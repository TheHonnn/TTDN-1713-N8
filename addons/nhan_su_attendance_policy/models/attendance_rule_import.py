# -*- coding: utf-8 -*-
import base64
import json
import re
from io import BytesIO

import requests

from odoo import fields, models
from odoo.exceptions import UserError


class AttendanceRuleImport(models.Model):
    _name = 'attendance.rule.import'
    _description = 'Nhập luật chấm công bằng AI'
    _order = 'create_date desc'

    name = fields.Char(string='Tên hồ sơ', required=True, default='Nhập luật mới')
    company_id = fields.Many2one('res.company', string='Công ty', required=True, default=lambda self: self.env.company)

    file_name = fields.Char(string='Tên file')
    file_data = fields.Binary(string='File luật', attachment=True)
    extracted_text = fields.Text(string='Nội dung trích xuất', readonly=True)
    ai_result_json = fields.Text(string='Kết quả AI (JSON)', readonly=True)
    parsed_company_name = fields.Char(string='Công ty AI nhận diện', readonly=True)
    parsed_shift_name = fields.Char(string='Tên ca AI đề xuất', readonly=True)
    parsed_start_time = fields.Float(string='Giờ vào AI đề xuất', readonly=True)
    parsed_end_time = fields.Float(string='Giờ ra AI đề xuất', readonly=True)
    parsed_break_duration = fields.Float(string='Nghỉ giữa ca (giờ)', readonly=True)
    parsed_allow_late_minutes = fields.Integer(string='Cho phép đi muộn (phút)', readonly=True)
    parsed_allow_early_minutes = fields.Integer(string='Cho phép về sớm (phút)', readonly=True)
    parsed_is_default = fields.Boolean(string='Ca mặc định', readonly=True)
    parsed_workdays_text = fields.Text(string='Ngày làm việc', readonly=True)
    parsed_penalty_note = fields.Text(string='Ghi chú phạt / nội quy', readonly=True)
    parsed_penalty_lines_text = fields.Text(string='Các mức phạt AI tách được', readonly=True)
    parsed_summary = fields.Text(string='Diễn giải dễ đọc', readonly=True)

    target_rule_id = fields.Many2one(
        'attendance.rule',
        string='Ca làm việc cần cập nhật',
        domain="[('company_id', '=', company_id)]",
    )
    applied_rule_id = fields.Many2one('attendance.rule', string='Ca đã áp dụng', readonly=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('extracted', 'Đã trích xuất'),
        ('parsed', 'Đã phân tích AI'),
        ('applied', 'Đã áp dụng'),
    ], default='draft', string='Trạng thái')

    def action_extract_text(self):
        for record in self:
            if not record.file_data:
                raise UserError('Vui lòng tải file luật trước khi trích xuất.')

            binary = base64.b64decode(record.file_data)
            ext = (record.file_name or '').lower()
            text = record._extract_text(binary, ext)
            if not text.strip():
                raise UserError('Không trích xuất được nội dung từ file.')

            record.write({'extracted_text': text, 'state': 'extracted'})

    def action_parse_with_ai(self):
        for record in self:
            if not record.extracted_text:
                raise UserError('Chưa có nội dung để phân tích. Hãy bấm Trích xuất trước.')

            parsed = record._parse_rule_with_ai(record.extracted_text)
            record.write({
                'ai_result_json': json.dumps(parsed, ensure_ascii=False, indent=2),
                **record._build_parsed_display_vals(parsed),
                'state': 'parsed',
            })

    def action_apply_to_rule(self):
        self.ensure_one()
        if not self.ai_result_json:
            raise UserError('Chưa có kết quả AI để áp dụng.')

        try:
            parsed = json.loads(self.ai_result_json)
        except json.JSONDecodeError as exc:
            raise UserError(f'Kết quả AI không hợp lệ: {exc}')

        vals = self._build_rule_vals(parsed)
        penalty_lines = self._normalize_penalty_lines(parsed.get('penalty_lines'))

        penalty_wizard_lines = [
            (0, 0, {
                'violation_type': line['violation_type'],
                'min_minutes': line['min_minutes'],
                'max_minutes': line['max_minutes'] or 0,
                'deduct_work_day': line['deduct_work_day'],
                'note': line.get('note') or False,
            })
            for line in penalty_lines
        ]

        wizard = self.env['attendance.rule.import.review.wizard'].create({
            'import_record_id': self.id,
            'company_id': self.company_id.id,
            'target_rule_id': self.target_rule_id.id if self.target_rule_id else False,
            'shift_name': vals.get('shift_name') or f"Ca tự động - {self.company_id.name}",
            'start_time': vals.get('start_time', 8.0),
            'end_time': vals.get('end_time', 17.0),
            'break_duration': vals.get('break_duration', 1.0),
            'allow_late_minutes': vals.get('allow_late_minutes', 0),
            'allow_early_minutes': vals.get('allow_early_minutes', 0),
            'is_default': vals.get('is_default', False),
            'monday_work': vals.get('monday_work', True),
            'tuesday_work': vals.get('tuesday_work', True),
            'wednesday_work': vals.get('wednesday_work', True),
            'thursday_work': vals.get('thursday_work', True),
            'friday_work': vals.get('friday_work', True),
            'saturday_work': vals.get('saturday_work', False),
            'sunday_work': vals.get('sunday_work', False),
            'notes': vals.get('notes') or False,
            'penalty_line_ids': penalty_wizard_lines,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Xem xét trước khi Áp dụng',
            'res_model': 'attendance.rule.import.review.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _extract_text(self, binary, ext):
        if ext.endswith(('.txt', '.md', '.csv', '.json')):
            return binary.decode('utf-8', errors='ignore')

        if ext.endswith('.pdf'):
            try:
                from pypdf import PdfReader  # type: ignore[import-not-found]
            except ImportError:
                raise UserError(
                    'Không thể đọc file PDF vì thiếu thư viện `pypdf`.\n'
                    'Vui lòng cài thêm: pip install pypdf\n'
                    'Sau khi cài, hãy khởi động lại Odoo service rồi thử lại.'
                )

            reader = PdfReader(BytesIO(binary))
            pages = [page.extract_text() or '' for page in reader.pages]
            return '\n'.join(pages)

        if ext.endswith('.docx'):
            try:
                from docx import Document  # type: ignore[import-not-found]
            except ImportError:
                raise UserError(
                    'Không thể đọc file DOCX vì thiếu thư viện `python-docx`.\n'
                    'Vui lòng cài thêm: pip install python-docx\n'
                    'Sau khi cài, hãy khởi động lại Odoo service rồi thử lại.'
                )

            doc = Document(BytesIO(binary))
            return '\n'.join([p.text for p in doc.paragraphs])

        raise UserError('Định dạng file chưa hỗ trợ. Hãy dùng PDF, DOCX, TXT, JSON hoặc CSV.')

    def _parse_rule_with_ai(self, text):
        api_url = self.env['ir.config_parameter'].sudo().get_param('attendance_policy.ai_api_url')
        api_key = self.env['ir.config_parameter'].sudo().get_param('attendance_policy.ai_api_key')
        model = self.env['ir.config_parameter'].sudo().get_param('attendance_policy.ai_model') or 'gpt-4o-mini'
        company_name = self.company_id.name or ''

        if api_url and api_key:
            payload = {
                'model': model,
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            'Bạn là AI parser nội quy chấm công. '\
                            'Hãy ưu tiên nhận diện đúng tên công ty, giờ làm, giờ nghỉ, quy định đi muộn/về sớm, và ghi chú xử phạt nếu văn bản có nêu. '\
                            'Chỉ trả về JSON hợp lệ, không markdown, theo schema: '\
                            '{"company_name":str,"shift_name":str,"description":str,"start_time":float,"end_time":float,'\
                            '"break_duration":float,"allow_late_minutes":int,"allow_early_minutes":int,'\
                            '"is_default":bool,"penalty_note":str,"penalty_lines":[{"violation_type":"late|early","min_minutes":int,'\
                            '"max_minutes":int|null,"deduct_work_day":float,"note":str}],"workdays":{"monday":bool,"tuesday":bool,'\
                            '"wednesday":bool,"thursday":bool,"friday":bool,"saturday":bool,"sunday":bool}}'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': (
                            f'Tên công ty cần phân tích: {company_name}. '\
                            'Nếu văn bản không ghi rõ tên công ty thì giữ đúng tên công ty này trong JSON. '\
                            'Hãy trả về dữ liệu dễ áp dụng cho cấu hình chấm công. '\
                            f'\n\nNội dung luật:\n{text[:12000]}'
                        ),
                    },
                ],
                'temperature': 0.1,
            }
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=45)
                response.raise_for_status()
                data = response.json()
                raw = data['choices'][0]['message']['content']
                return self._safe_json_parse(raw)
            except Exception:
                # fallback về parser rule-based để không chặn luồng nghiệp vụ
                return self._heuristic_parse(text)

        return self._heuristic_parse(text)

    @staticmethod
    def _float_to_time_text(value):
        hours = int(value or 0)
        minutes = int(round(((value or 0) - hours) * 60))
        if minutes == 60:
            hours += 1
            minutes = 0
        return f'{hours:02d}:{minutes:02d}'

    def _build_workdays_text(self, workdays):
        labels = [
            ('monday', 'Thứ 2'),
            ('tuesday', 'Thứ 3'),
            ('wednesday', 'Thứ 4'),
            ('thursday', 'Thứ 5'),
            ('friday', 'Thứ 6'),
            ('saturday', 'Thứ 7'),
            ('sunday', 'Chủ nhật'),
        ]
        active_days = [label for key, label in labels if workdays.get(key)]
        return ', '.join(active_days) if active_days else 'Chưa xác định'

    def _build_penalty_lines_text(self, penalty_lines):
        label_map = {'late': 'Đi muộn', 'early': 'Về sớm'}
        rows = []
        for line in penalty_lines or []:
            violation_type = label_map.get(line.get('violation_type'), line.get('violation_type') or 'Vi phạm')
            min_minutes = int(line.get('min_minutes') or 0)
            max_minutes = line.get('max_minutes')
            deduct = float(line.get('deduct_work_day') or 0.0)
            range_text = f'{min_minutes}+ phút' if max_minutes in (None, False, '') else f'{min_minutes}-{int(max_minutes)} phút'
            note = line.get('note') or ''
            rows.append(f'- {violation_type}: {range_text} -> trừ {deduct:g} công' + (f' ({note})' if note else ''))
        return '\n'.join(rows) if rows else 'Chưa tách được mức phạt cụ thể.'

    def _normalize_penalty_lines(self, penalty_lines):
        normalized = []
        seen = set()
        for line in penalty_lines or []:
            violation_type = line.get('violation_type')
            if violation_type not in {'late', 'early'}:
                continue
            min_minutes = int(line.get('min_minutes') or 0)
            max_minutes = line.get('max_minutes')
            max_minutes = int(max_minutes) if max_minutes not in (None, False, '') else False
            deduct_work_day = float(line.get('deduct_work_day') or 0.0)
            note = line.get('note') or False
            key = (violation_type, min_minutes, max_minutes, deduct_work_day)
            if deduct_work_day < 0 or key in seen:
                continue
            seen.add(key)
            normalized.append({
                'violation_type': violation_type,
                'min_minutes': min_minutes,
                'max_minutes': max_minutes,
                'deduct_work_day': deduct_work_day,
                'note': note,
            })
        return sorted(normalized, key=lambda item: (item['violation_type'], item['min_minutes'], item['max_minutes'] or 99999))

    def _build_parsed_display_vals(self, parsed):
        workdays = parsed.get('workdays') or {}
        company_name = parsed.get('company_name') or self.company_id.name
        shift_name = parsed.get('shift_name') or f'Ca từ luật - {company_name}'
        start_time = float(parsed.get('start_time') or 8.0)
        end_time = float(parsed.get('end_time') or 17.0)
        break_duration = float(parsed.get('break_duration') or 1.0)
        allow_late = int(parsed.get('allow_late_minutes') or 0)
        allow_early = int(parsed.get('allow_early_minutes') or 0)
        penalty_note = parsed.get('penalty_note') or parsed.get('description') or 'Không thấy nội dung phạt riêng trong văn bản.'
        penalty_lines = self._normalize_penalty_lines(parsed.get('penalty_lines'))
        workdays_text = self._build_workdays_text(workdays)
        penalty_lines_text = self._build_penalty_lines_text(penalty_lines)

        summary_lines = [
            f'Công ty: {company_name}',
            f'Tên ca: {shift_name}',
            f'Giờ vào: {self._float_to_time_text(start_time)}',
            f'Giờ ra: {self._float_to_time_text(end_time)}',
            f'Nghỉ giữa ca: {break_duration:g} giờ',
            f'Cho phép đi muộn: {allow_late} phút',
            f'Cho phép về sớm: {allow_early} phút',
            f'Ngày làm việc: {workdays_text}',
            f'Ca mặc định: {"Có" if parsed.get("is_default") else "Không"}',
            f'Ghi chú phạt / diễn giải: {penalty_note}',
            f'Các mức phạt:\n{penalty_lines_text}',
        ]

        return {
            'parsed_company_name': company_name,
            'parsed_shift_name': shift_name,
            'parsed_start_time': start_time,
            'parsed_end_time': end_time,
            'parsed_break_duration': break_duration,
            'parsed_allow_late_minutes': allow_late,
            'parsed_allow_early_minutes': allow_early,
            'parsed_is_default': bool(parsed.get('is_default')),
            'parsed_workdays_text': workdays_text,
            'parsed_penalty_note': penalty_note,
            'parsed_penalty_lines_text': penalty_lines_text,
            'parsed_summary': '\n'.join(summary_lines),
        }

    def _extract_penalty_lines_from_text(self, text):
        text_l = (text or '').lower()
        penalty_lines = []

        patterns = [
            re.compile(
                r'(đi muộn|đi trễ|về sớm)[^\n\r]{0,50}?(\d{1,3})\s*[-–]\s*(\d{1,3})\s*phút[^\n\r]{0,60}?(?:trừ|phạt)\s*(\d+(?:[\.,]\d+)?)\s*công'
            ),
            re.compile(
                r'(đi muộn|đi trễ|về sớm)[^\n\r]{0,50}?(?:từ|trên)\s*(\d{1,3})\s*phút[^\n\r]{0,60}?(?:trừ|phạt)\s*(\d+(?:[\.,]\d+)?)\s*công'
            ),
        ]

        for match in patterns[0].finditer(text_l):
            violation_label, min_minutes, max_minutes, deduct = match.groups()
            penalty_lines.append({
                'violation_type': 'early' if 'về sớm' in violation_label else 'late',
                'min_minutes': int(min_minutes),
                'max_minutes': int(max_minutes),
                'deduct_work_day': float(deduct.replace(',', '.')),
                'note': 'Tách từ nội quy bằng heuristic parser',
            })

        for match in patterns[1].finditer(text_l):
            violation_label, min_minutes, deduct = match.groups()
            penalty_lines.append({
                'violation_type': 'early' if 'về sớm' in violation_label else 'late',
                'min_minutes': int(min_minutes),
                'max_minutes': False,
                'deduct_work_day': float(deduct.replace(',', '.')),
                'note': 'Tách từ nội quy bằng heuristic parser',
            })

        return self._normalize_penalty_lines(penalty_lines)

    def _safe_json_parse(self, raw):
        raw = (raw or '').strip()
        try:
            return json.loads(raw)
        except Exception:
            match = re.search(r'\{[\s\S]*\}', raw)
            if not match:
                raise UserError('AI không trả về JSON hợp lệ.')
            return json.loads(match.group(0))

    def _heuristic_parse(self, text):
        text_l = (text or '').lower()

        start_time = 8.0
        end_time = 17.0
        break_duration = 1.0
        allow_late = 0
        allow_early = 0

        time_match = re.search(r'(\d{1,2})[:h](\d{2})\s*[-–]\s*(\d{1,2})[:h](\d{2})', text_l)
        if time_match:
            sh, sm, eh, em = [int(x) for x in time_match.groups()]
            start_time = sh + sm / 60.0
            end_time = eh + em / 60.0

        late_match = re.search(r'(đi muộn|đi trễ)[^\d]{0,20}(\d{1,3})\s*phút', text_l)
        if late_match:
            allow_late = int(late_match.group(2))

        early_match = re.search(r'(về sớm)[^\d]{0,20}(\d{1,3})\s*phút', text_l)
        if early_match:
            allow_early = int(early_match.group(2))

        lunch_match = re.search(r'(nghỉ trưa|nghỉ giữa ca)[^\d]{0,20}(\d{1,2})\s*(giờ|h)', text_l)
        if lunch_match:
            break_duration = float(lunch_match.group(2))

        sat_work = 'thứ 7 làm' in text_l or 'thu 7 lam' in text_l
        sun_work = 'chủ nhật làm' in text_l or 'chu nhat lam' in text_l
        penalty_lines = self._extract_penalty_lines_from_text(text)

        return {
            'company_name': self.company_id.name,
            'shift_name': f'Ca từ file luật - {self.company_id.name}',
            'description': 'Tự động phân tích từ file luật',
            'start_time': start_time,
            'end_time': end_time,
            'break_duration': break_duration,
            'allow_late_minutes': allow_late,
            'allow_early_minutes': allow_early,
            'is_default': True,
            'penalty_note': 'Chưa tách riêng được chính sách phạt từ heuristic parser.',
            'penalty_lines': penalty_lines,
            'workdays': {
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': sat_work,
                'sunday': sun_work,
            },
        }

    def _build_rule_vals(self, parsed):
        workdays = parsed.get('workdays') or {}
        penalty_lines = self._normalize_penalty_lines(parsed.get('penalty_lines'))

        vals = {
            'company_id': self.company_id.id,
            'shift_name': parsed.get('shift_name') or f"Ca từ luật - {self.company_id.name}",
            'description': parsed.get('description') or False,
            'start_time': float(parsed.get('start_time') or 8.0),
            'end_time': float(parsed.get('end_time') or 17.0),
            'break_duration': float(parsed.get('break_duration') or 1.0),
            'allow_late_minutes': int(parsed.get('allow_late_minutes') or 0),
            'allow_early_minutes': int(parsed.get('allow_early_minutes') or 0),
            'is_default': bool(parsed.get('is_default')),
            'monday_work': bool(workdays.get('monday', True)),
            'tuesday_work': bool(workdays.get('tuesday', True)),
            'wednesday_work': bool(workdays.get('wednesday', True)),
            'thursday_work': bool(workdays.get('thursday', True)),
            'friday_work': bool(workdays.get('friday', True)),
            'saturday_work': bool(workdays.get('saturday', False)),
            'sunday_work': bool(workdays.get('sunday', False)),
            'notes': parsed.get('penalty_note') or False,
        }

        if penalty_lines:
            vals['penalty_line_ids'] = [
                (5, 0, 0),
                *[
                    (0, 0, {
                        'violation_type': line['violation_type'],
                        'min_minutes': line['min_minutes'],
                        'max_minutes': line['max_minutes'],
                        'deduct_work_day': line['deduct_work_day'],
                        'note': line['note'],
                    })
                    for line in penalty_lines
                ],
            ]

        if vals['end_time'] <= vals['start_time']:
            raise UserError('Giờ tan ca phải lớn hơn giờ vào ca.')
        return vals
