# -*- coding: utf-8 -*-
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError


class NhanSuAiChatMessage(models.Model):
    _name = 'nhan_su.ai.chat.message'
    _description = 'Tin nhắn trong chat AI nhân sự'
    _order = 'id asc'

    chat_id = fields.Many2one(
        'nhan_su.ai.chat',
        string='Cuộc trò chuyện',
        required=True,
        ondelete='cascade',
    )
    role = fields.Selection(
        [('user', 'Bạn'), ('assistant', 'Trợ lý AI')],
        string='Người gửi',
        required=True,
    )
    content = fields.Text(string='Nội dung', required=True)


class NhanSuAiChat(models.Model):
    _name = 'nhan_su.ai.chat'
    _description = 'Chat AI hỏi đáp về nhân sự công ty'
    _order = 'write_date desc'

    name = fields.Char(
        string='Tiêu đề',
        required=True,
        default='Trò chuyện mới',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
    )
    user_input = fields.Char(
        string='Câu hỏi',
        help='Nhập câu hỏi về nhân viên, ca làm, quy định... rồi bấm "Hỏi AI".',
    )
    message_ids = fields.One2many(
        'nhan_su.ai.chat.message',
        'chat_id',
        string='Tin nhắn',
    )
    conversation_log = fields.Text(
        string='Lịch sử cuộc trò chuyện',
        compute='_compute_conversation_log',
    )

    @api.depends('message_ids', 'message_ids.role', 'message_ids.content')
    def _compute_conversation_log(self):
        for rec in self:
            if not rec.message_ids:
                rec.conversation_log = (
                    '(Chưa có cuộc trò chuyện nào.\n'
                    'Nhập câu hỏi bên dưới và bấm "Hỏi AI" để bắt đầu.)'
                )
                continue
            lines = []
            for msg in rec.message_ids:
                if msg.role == 'user':
                    lines.append(f'[Bạn hỏi]\n{msg.content}')
                else:
                    lines.append(f'[Trợ lý AI]\n{msg.content}')
                lines.append('─' * 60)
            rec.conversation_log = '\n'.join(lines)

    # ------------------------------------------------------------------
    # Hành động
    # ------------------------------------------------------------------

    def _ask_with_question(self, question):
        self.ensure_one()
        question = (question or '').strip()
        if not question:
            raise UserError('Vui lòng nhập câu hỏi trước khi gửi.')

        self.env['nhan_su.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'user',
            'content': question,
        })

        system_prompt = self._build_system_prompt()
        api_messages = [{'role': 'system', 'content': system_prompt}]
        for msg in self.message_ids:
            api_messages.append({'role': msg.role, 'content': msg.content})

        try:
            answer = self._call_ai_api(api_messages, question)
        except Exception as exc:
            answer = (
                'Hệ thống AI đang gặp lỗi tạm thời, nhưng bạn vẫn có thể tiếp tục hỏi.\n'
                f'Chi tiết kỹ thuật: {exc}'
            )

        self.env['nhan_su.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'assistant',
            'content': answer,
        })

        if self.name == 'Trò chuyện mới':
            title = question[:70] + ('...' if len(question) > 70 else '')
            self.write({'name': title})

    def action_ask(self):
        self.ensure_one()
        question = self.user_input
        self._ask_with_question(question)
        self.write({'user_input': False})

    def action_open_quick_ask_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nhan_su.ai.chat.quick.ask.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chat_id': self.id,
            },
        }

    def action_open_api_config_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nhan_su.ai.chat.api.config.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_clear(self):
        self.ensure_one()
        self.message_ids.unlink()
        self.write({'user_input': False, 'name': 'Trò chuyện mới'})

    # ------------------------------------------------------------------
    # Trình tạo ngữ cảnh
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_record_name(record, fallback_fields=None):
        if not record:
            return '—'
        fallback_fields = fallback_fields or []
        for field_name in fallback_fields:
            if field_name in record._fields:
                value = record[field_name]
                if value:
                    return str(value)
        return record.display_name or '—'

    def _build_system_prompt(self):
        company = self.company_id
        env = self.env

        # Danh sách nhân viên
        employees = env['nhan_vien'].sudo().search(
            [('company_id', '=', company.id)], limit=300
        )
        emp_lines = []
        for e in employees:
            dept = self._safe_record_name(e.phong_ban_id, ['ten_phong_ban', 'name'])
            pos = self._safe_record_name(e.chuc_vu_id, ['ten_chuc_vu', 'name'])
            emp_name = e.ho_va_ten or e.display_name
            emp_lines.append(
                f'  • {emp_name} (Mã: {e.ma_dinh_danh}) | Phòng: {dept} | Chức vụ: {pos}'
            )

        # Phòng ban
        dept_lines = []
        try:
            depts = env['phong_ban'].sudo().search([])
            dept_lines = [
                f"  • {self._safe_record_name(d, ['ten_phong_ban', 'name'])}"
                for d in depts
            ]
        except Exception:
            pass

        # Chức vụ
        pos_lines = []
        try:
            positions = env['chuc_vu'].sudo().search([])
            pos_lines = [
                f"  • {self._safe_record_name(p, ['ten_chuc_vu', 'name'])}"
                for p in positions
            ]
        except Exception:
            pass

        # Ca làm việc và quy định chấm công
        att_lines = []
        try:
            rules = env['attendance.rule'].sudo().search(
                [('company_id', '=', company.id)]
            )
            for r in rules:
                h_in = int(r.start_time)
                m_in = int(round((r.start_time - h_in) * 60))
                h_out = int(r.end_time)
                m_out = int(round((r.end_time - h_out) * 60))
                late_ok = getattr(r, 'allow_late_minutes', 0) or 0
                early_ok = getattr(r, 'allow_early_minutes', 0) or 0
                att_lines.append(
                    f'  • Ca "{r.shift_name}": {h_in:02d}:{m_in:02d} – {h_out:02d}:{m_out:02d}'
                    f' | Chấp nhận muộn: {late_ok} phút | Chấp nhận sớm: {early_ok} phút'
                )
                # Bậc phạt
                try:
                    for pen in r.penalty_line_ids:
                        vtype = 'Đi muộn' if pen.violation_type == 'late' else 'Về sớm'
                        rng = f'{pen.min_minutes}+ phút'
                        if pen.max_minutes:
                            rng = f'{pen.min_minutes}-{pen.max_minutes} phút'
                        att_lines.append(
                            f'    – Phạt {vtype} {rng}: trừ {pen.deduct_work_day} công'
                        )
                except Exception:
                    pass
        except Exception:
            pass

        # Quy tắc lương (tùy chọn)
        pay_lines = []
        try:
            prules = env['payroll.position.rule'].sudo().search(
                [('company_id', '=', company.id)], limit=50
            )
            for pr in prules:
                pay_lines.append(f"  • {self._safe_record_name(pr, ['name'])}")
        except Exception:
            pass

        # Ghép lại prompt
        sections = [
            f'Bạn là trợ lý AI nhân sự của công ty **{company.name}**.',
            'Hãy trả lời bằng tiếng Việt, ngắn gọn và chính xác dựa trên dữ liệu thực của công ty được cung cấp dưới đây.',
            'Nếu câu hỏi nằm ngoài phạm vi dữ liệu này, hãy trả lời dựa trên kiến thức nhân sự chung và nêu rõ đó là ý kiến chung.',
            '',
            f'════════ DỮ LIỆU THỰC CỦA CÔNG TY: {company.name} ════════',
            f'Tổng số nhân viên: {len(employees)}',
            '',
            'DANH SÁCH NHÂN VIÊN:',
            *(emp_lines or ['  (Chưa có nhân viên nào.)']),
            '',
            'PHÒNG BAN:',
            *(dept_lines or ['  (Chưa có phòng ban.)']),
            '',
            'CHỨC VỤ:',
            *(pos_lines or ['  (Chưa có chức vụ.)']),
            '',
            'CA LÀM VIỆC & QUY ĐỊNH CHẤM CÔNG:',
            *(att_lines or ['  (Chưa có ca làm việc.)']),
        ]
        if pay_lines:
            sections += ['', 'QUY TẮC LƯƠNG:', *pay_lines]

        return '\n'.join(sections)

    def _build_company_snapshot(self):
        company = self.company_id
        env = self.env
        employees = env['nhan_vien'].sudo().search([('company_id', '=', company.id)], limit=500)
        departments = env['phong_ban'].sudo().search([])
        positions = env['chuc_vu'].sudo().search([])
        rules = env['attendance.rule'].sudo().search([('company_id', '=', company.id)])
        return {
            'company_name': company.name,
            'employee_count': len(employees),
            'employees': employees,
            'departments': departments,
            'positions': positions,
            'rules': rules,
        }

    def _offline_answer(self, question):
        q = (question or '').lower()
        data = self._build_company_snapshot()

        if 'bao nhiêu' in q and 'nhân viên' in q:
            return (
                f"Công ty {data['company_name']} hiện có {data['employee_count']} nhân viên "
                '(theo dữ liệu đang lưu trong hệ thống).'
            )

        if 'phòng ban' in q:
            names = [self._safe_record_name(d, ['ten_phong_ban', 'name']) for d in data['departments']]
            if not names:
                return 'Hiện chưa có phòng ban nào trong dữ liệu.'
            return 'Danh sách phòng ban: ' + ', '.join(names)

        if 'chức vụ' in q:
            names = [self._safe_record_name(p, ['ten_chuc_vu', 'name']) for p in data['positions']]
            if not names:
                return 'Hiện chưa có chức vụ nào trong dữ liệu.'
            return 'Danh sách chức vụ: ' + ', '.join(names)

        if 'ca làm' in q or 'ca làm việc' in q or 'đi muộn' in q or 'về sớm' in q:
            if not data['rules']:
                return 'Hiện chưa có cấu hình ca làm việc trong hệ thống.'
            lines = []
            for r in data['rules'][:10]:
                h_in = int(r.start_time)
                m_in = int(round((r.start_time - h_in) * 60))
                h_out = int(r.end_time)
                m_out = int(round((r.end_time - h_out) * 60))
                lines.append(
                    f"- {r.shift_name}: {h_in:02d}:{m_in:02d} - {h_out:02d}:{m_out:02d}, "
                    f"muộn {r.allow_late_minutes} phút, sớm {r.allow_early_minutes} phút"
                )
            return 'Thông tin ca làm việc:\n' + '\n'.join(lines)

        return (
            'Mình đang chạy ở chế độ trợ lý nội bộ (không cần API ngoài) nên vẫn hỗ trợ câu hỏi cơ bản.\n'
            'Bạn có thể hỏi: số lượng nhân viên, danh sách phòng ban, chức vụ, ca làm việc, quy định đi muộn/về sớm.\n'
            'Nếu muốn trả lời chuyên sâu hơn, hãy cấu hình attendance_policy.ai_api_url và attendance_policy.ai_api_key.'
        )

    # ------------------------------------------------------------------
    # Gọi API AI bên ngoài
    # ------------------------------------------------------------------

    def _call_ai_api(self, messages, question=None):
        config = self.env['ir.config_parameter'].sudo()
        api_url = config.get_param('attendance_policy.ai_api_url')
        api_key = config.get_param('attendance_policy.ai_api_key')
        model = config.get_param('attendance_policy.ai_model') or 'gpt-4o-mini'

        if not api_url or not api_key:
            return self._offline_answer(question or '')

        try:
            resp = requests.post(
                api_url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': messages,
                    'temperature': 0.3,
                    'max_tokens': 1500,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except requests.exceptions.Timeout:
            return self._offline_answer(question or '')
        except requests.exceptions.HTTPError as exc:
            return (
                f'Không gọi được AI bên ngoài ({exc}).\n'
                'Mình chuyển sang trả lời bằng dữ liệu nội bộ:\n\n'
                + self._offline_answer(question or '')
            )
        except Exception as exc:
            return (
                f'AI bên ngoài tạm lỗi ({exc}).\n'
                'Mình chuyển sang trợ lý nội bộ:\n\n'
                + self._offline_answer(question or '')
            )
