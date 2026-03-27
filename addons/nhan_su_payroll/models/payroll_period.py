import base64
from io import BytesIO
from calendar import monthrange
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


class PayrollPeriod(models.Model):
    _name = 'payroll.period'
    _description = 'Kỳ lương'
    _order = 'year desc, month desc, id desc'

    name = fields.Char(string='Tên kỳ lương', compute='_compute_name', store=True)
    month = fields.Selection(
        [(str(number), f'Tháng {number}') for number in range(1, 13)],
        string='Tháng',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(string='Năm', required=True, default=lambda self: fields.Date.today().year)
    date_start = fields.Date(string='Từ ngày', compute='_compute_date_range', store=True)
    date_end = fields.Date(string='Đến ngày', compute='_compute_date_range', store=True)
    date_start_display = fields.Char(string='Từ ngày (DD/MM/YYYY)', compute='_compute_date_display')
    date_end_display = fields.Char(string='Đến ngày (DD/MM/YYYY)', compute='_compute_date_display')
    line_ids = fields.One2many('payroll.employee.line', 'period_id', string='Dòng lương')
    total_employee = fields.Integer(string='Số nhân viên', compute='_compute_summary', store=True)
    total_salary = fields.Float(string='Tổng lương thực lĩnh', compute='_compute_summary', store=True)
    notification_date = fields.Date(string='Ngày gửi bảng lương')
    notification_auto_send = fields.Boolean(string='Tự gửi theo ngày', default=True)
    notification_status = fields.Selection(
        [
            ('not_sent', 'Chưa gửi'),
            ('partial', 'Gửi một phần'),
            ('sent', 'Đã gửi'),
        ],
        string='Trạng thái gửi thông báo',
        default='not_sent',
        copy=False,
        readonly=True,
    )
    notification_sent_at = fields.Datetime(string='Lần gửi gần nhất', copy=False, readonly=True)
    notification_sent_count = fields.Integer(string='Đã gửi thành công', copy=False, readonly=True)
    notification_failed_count = fields.Integer(string='Gửi lỗi', copy=False, readonly=True)
    state = fields.Selection(
        [('draft', 'Nháp'), ('computed', 'Đã tính'), ('confirmed', 'Đã chốt')],
        string='Trạng thái',
        default='draft',
        required=True,
    )
    _sql_constraints = [
        ('payroll_period_unique', 'unique(month, year)', 'Kỳ lương của tháng này đã tồn tại.'),
    ]

    @api.depends('month', 'year')
    def _compute_date_range(self):
        for record in self:
            if not record.month or not record.year:
                record.date_start = False
                record.date_end = False
                continue
            month_number = int(record.month)
            last_day = monthrange(record.year, month_number)[1]
            record.date_start = date(record.year, month_number, 1)
            record.date_end = date(record.year, month_number, last_day)

    @api.depends('month', 'year')
    def _compute_name(self):
        for record in self:
            if record.month and record.year:
                record.name = f'Bảng lương {record.month}/{record.year}'
            else:
                record.name = 'Kỳ lương'

    @api.depends('date_start', 'date_end')
    def _compute_date_display(self):
        for record in self:
            record.date_start_display = record.date_start.strftime('%d/%m/%Y') if record.date_start else False
            record.date_end_display = record.date_end.strftime('%d/%m/%Y') if record.date_end else False

    @api.depends('line_ids.net_salary')
    def _compute_summary(self):
        for record in self:
            record.total_employee = len(record.line_ids)
            record.total_salary = sum(record.line_ids.mapped('net_salary'))

    @api.constrains('year')
    def _check_year(self):
        for record in self:
            if record.year < 2000 or record.year > 2100:
                raise ValidationError('Năm kỳ lương không hợp lệ.')

    def action_generate_lines(self):
        position_rule_model = self.env['payroll.position.rule'].sudo()
        penalty_rule = self.env['payroll.penalty.rule'].sudo().get_active_rule()
        daily_sheet_model = self.env['daily.sheet'].sudo()
        employee_model = self.env['nhan_vien'].sudo()
        policy_service = self.env['attendance.policy.service'].sudo()

        for period in self:
            if not period.date_start or not period.date_end:
                raise UserError('Kỳ lương chưa có ngày bắt đầu và ngày kết thúc hợp lệ.')

            period.line_ids.unlink()
            line_values = []

            employees = employee_model.search([], order='ma_dinh_danh asc, id asc')
            for employee in employees:
                hr_employee = policy_service.get_or_create_hr_employee(employee)
                current_date = period.date_start
                while current_date <= period.date_end:
                    policy_service.generate_daily_sheet(hr_employee.id, current_date)
                    current_date += timedelta(days=1)

                position_rule = position_rule_model.search([
                    ('chuc_vu_id', '=', employee.chuc_vu_id.id),
                    ('active', '=', True),
                ], limit=1)
                if not position_rule:
                    continue

                sheets = daily_sheet_model.search([
                    ('nhan_vien_id', '=', employee.id),
                    ('work_date', '>=', period.date_start),
                    ('work_date', '<=', period.date_end),
                ])

                present_days = len(sheets.filtered(lambda sheet: sheet.status == 'present'))
                absent_days = len(sheets.filtered(lambda sheet: sheet.status == 'absent'))
                incomplete_days = len(sheets.filtered(lambda sheet: sheet.status == 'incomplete'))
                payable_days = sum(sheets.mapped('payable_work_day'))
                deducted_days = sum(sheets.mapped('deduction_work_day'))
                total_minutes_late = sum(sheets.mapped('minutes_late'))
                total_minutes_early = sum(sheets.mapped('minutes_early'))

                daily_rate = position_rule.base_salary / position_rule.standard_work_days
                salary_amount = daily_rate * payable_days
                bonus_amount = position_rule.bonus_amount
                penalty_amount = (
                    (total_minutes_late * penalty_rule.late_penalty_per_minute) +
                    (total_minutes_early * penalty_rule.early_penalty_per_minute) +
                    (absent_days * penalty_rule.absent_penalty_per_day) +
                    (incomplete_days * penalty_rule.incomplete_penalty_per_day)
                )

                # Xử lý trường hợp lương âm: trừ vào thưởng, không để lương âm
                # Nếu lương sau phạt âm, phạt sẽ trừ vào thưởng
                salary_after_penalty = salary_amount - penalty_amount
                if salary_after_penalty < 0:
                    # Phạt vượt quá lương → trừ vào thưởng
                    # Thưởng cuối cùng = thưởng gốc + (lương - phạt) = max(0, ...)
                    adjusted_bonus = max(0, bonus_amount + salary_after_penalty)
                    net_salary = adjusted_bonus
                else:
                    # Lương sau phạt >= 0 → tính bình thường
                    net_salary = salary_amount + bonus_amount - penalty_amount

                line_values.append({
                    'period_id': period.id,
                    'nhan_vien_id': employee.id,
                    'chuc_vu_id': employee.chuc_vu_id.id,
                    'position_rule_id': position_rule.id,
                    'base_salary': position_rule.base_salary,
                    'salary_amount': salary_amount,
                    'bonus_amount': bonus_amount,
                    'penalty_amount': penalty_amount,
                    'net_salary': net_salary,
                    'standard_work_days': position_rule.standard_work_days,
                    'payable_work_days': payable_days,
                    'deducted_work_days': deducted_days,
                    'present_days': present_days,
                    'absent_days': absent_days,
                    'incomplete_days': incomplete_days,
                    'total_minutes_late': total_minutes_late,
                    'total_minutes_early': total_minutes_early,
                })

            if line_values:
                self.env['payroll.employee.line'].sudo().create(line_values)
            period.state = 'computed'

    def action_confirm(self):
        for period in self:
            if not period.line_ids:
                raise UserError('Chưa có dòng bảng lương để chốt.')
            period.state = 'confirmed'

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'notification_status': 'not_sent',
            'notification_sent_at': False,
            'notification_sent_count': 0,
            'notification_failed_count': 0,
        })

    def action_send_salary_notifications(self):
        mail_model = self.env['mail.mail'].sudo()

        for period in self:
            if period.state != 'confirmed':
                raise UserError('Chỉ được gửi thông báo khi bảng lương đã chốt.')
            if not period.line_ids:
                raise UserError('Không có dòng lương để gửi thông báo.')

            sent_count = 0
            failed_count = 0
            for line in period.line_ids:
                employee_email = (line.nhan_vien_id.email or '').strip()
                if not employee_email:
                    line.write({
                        'notification_status': 'failed',
                        'notification_error': 'Nhân sự chưa có email để nhận bảng lương.',
                        'notification_sent_at': False,
                    })
                    failed_count += 1
                    continue

                pdf_content = period._generate_salary_pdf(line)
                attachment = self.env['ir.attachment'].sudo().create({
                    'name': f'Bang_luong_{line.nhan_vien_id.ma_dinh_danh}_{period.month}_{period.year}.pdf',
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'mimetype': 'application/pdf',
                    'res_model': 'payroll.employee.line',
                    'res_id': line.id,
                })

                mail_values = {
                    'subject': f'Thông báo lương tháng {period.month}/{period.year} - {line.nhan_vien_id.ho_va_ten}',
                    'email_to': employee_email,
                    'body_html': period._build_salary_mail_body(line),
                    'attachment_ids': [(4, attachment.id)],
                    'auto_delete': False,
                }

                try:
                    mail = mail_model.create(mail_values)
                    mail.send()
                    line.write({
                        'notification_status': 'sent',
                        'notification_sent_at': fields.Datetime.now(),
                        'notification_error': False,
                    })
                    sent_count += 1
                except Exception as exc:
                    line.write({
                        'notification_status': 'failed',
                        'notification_sent_at': False,
                        'notification_error': str(exc),
                    })
                    failed_count += 1

            period.write({
                'notification_status': 'sent' if failed_count == 0 else ('partial' if sent_count else 'not_sent'),
                'notification_sent_at': fields.Datetime.now(),
                'notification_sent_count': sent_count,
                'notification_failed_count': failed_count,
            })

    def _build_salary_mail_body(self, line):
        self.ensure_one()
        employee_name = line.nhan_vien_id.ho_va_ten or line.nhan_vien_id.display_name
        company_name = line.nhan_vien_id.company_id.name or self.env.company.name
        
        # Tính thưởng thực tế sau khi bị trừ phạt (nếu có)
        salary_after_penalty = line.salary_amount - line.penalty_amount
        if salary_after_penalty < 0:
            actual_bonus = max(0, line.bonus_amount + salary_after_penalty)
        else:
            actual_bonus = line.bonus_amount
        
        return f"""
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#222;">
                <p>Kính gửi {employee_name},</p>
                <p>{company_name} gửi đến bạn thông báo lương kỳ <strong>{self.month}/{self.year}</strong>.</p>
                <table style="border-collapse:collapse;inline-size:100%;max-inline-size:620px;">
                    <tr>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>Lương cơ bản tháng</strong></td>
                        <td style="padding:8px;border:1px solid #ddd;text-align:end;">{self._format_currency(line.base_salary)}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>Lương theo công</strong></td>
                        <td style="padding:8px;border:1px solid #ddd;text-align:end;">{self._format_currency(line.salary_amount)}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>Khấu trừ / phạt</strong></td>
                        <td style="padding:8px;border:1px solid #ddd;text-align:end;">{self._format_currency(line.penalty_amount)}</td>
                    </tr>
                    <tr>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>Thưởng</strong></td>
                        <td style="padding:8px;border:1px solid #ddd;text-align:end;">
                            {self._format_currency(actual_bonus)}
                            {'' if actual_bonus == line.bonus_amount else f' <span style="color:#d9534f;">(gốc: {self._format_currency(line.bonus_amount)})</span>'}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>Thực lĩnh</strong></td>
                        <td style="padding:8px;border:1px solid #ddd;text-align:end;color:#0b6b2e;"><strong>{self._format_currency(line.net_salary)}</strong></td>
                    </tr>
                </table>
                <p>Phiếu lương chi tiết được đính kèm trong file PDF.</p>
                <p>Trân trọng.</p>
            </div>
        """

    @staticmethod
    def _format_currency(amount):
        value = float(amount or 0.0)
        return '{:,.0f} VND'.format(value).replace(',', '.')

    def _generate_salary_pdf(self, line):
        """Tạo phiếu lương dưới dạng PDF với hỗ trợ tiếng Việt đầy đủ."""
        self.ensure_one()
        buffer = BytesIO()
        
        # Thiết lập font hỗ trợ tiếng Việt
        try:
            # Thử dùng font hệ thống hỗ trợ Unicode
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                font_name = 'DejaVu'
                font_bold = 'DejaVu'
            else:
                # Fallback sang Helvetica nếu không có DejaVu
                font_name = 'Helvetica'
                font_bold = 'Helvetica-Bold'
        except Exception:
            font_name = 'Helvetica'
            font_bold = 'Helvetica-Bold'
        
        pdf = canvas.Canvas(buffer, pagesize=A4)
        page_width, page_height = A4
        y = page_height - 50

        def write_text(text, size=11, bold=False, gap=18):
            """Ghi text lên PDF với font được chọn."""
            nonlocal y
            current_font = font_bold if bold else font_name
            try:
                current_size = f'{current_font}-Bold' if bold and current_font != 'DejaVu' else current_font
                pdf.setFont(current_size, size)
            except Exception:
                pdf.setFont(font_name, size)
            pdf.drawString(50, y, text)
            y -= gap

        # Lấy thông tin nhân viên
        employee_name = line.nhan_vien_id.ho_va_ten or line.nhan_vien_id.display_name or ''
        job_name = getattr(line.chuc_vu_id, 'ten_chuc_vu', False) or line.chuc_vu_id.display_name or ''
        
        # Tính thưởng thực tế sau khi bị trừ phạt (nếu có)
        salary_after_penalty = line.salary_amount - line.penalty_amount
        if salary_after_penalty < 0:
            actual_bonus = max(0, line.bonus_amount + salary_after_penalty)
        else:
            actual_bonus = line.bonus_amount

        # Vẽ tiêu đề và thông tin chung
        write_text('PHIẾU LƯƠNG NHÂN SỰ', size=16, bold=True, gap=26)
        write_text(f'Kỳ lương: Tháng {self.month}/{self.year}')
        write_text(f'Nhân sự: {employee_name}')
        write_text(f'Mã định danh: {line.nhan_vien_id.ma_dinh_danh or ""}')
        write_text(f'Chức vụ: {job_name}')
        
        # Khoảng trống
        y -= 8
        
        # Vẽ chi tiết lương
        write_text(f'Lương cơ bản tháng: {self._format_currency(line.base_salary)}')
        write_text(f'Lương theo công: {self._format_currency(line.salary_amount)}')
        write_text(f'Khấu trừ / phạt: {self._format_currency(line.penalty_amount)}')
        write_text(f'Thưởng: {self._format_currency(actual_bonus)}')
        if actual_bonus != line.bonus_amount:
            write_text(f'  (gốc: {self._format_currency(line.bonus_amount)})')
        write_text(f'Công hưởng lương: {line.payable_work_days}')
        write_text(f'Công bị trừ: {line.deducted_work_days}')
        write_text(f'Tổng phút đi muộn: {line.total_minutes_late}')
        write_text(f'Tổng phút về sớm: {line.total_minutes_early}')
        
        # Khoảng trống
        y -= 8
        
        # Hiển thị tổng thực lĩnh
        write_text(f'THỰC LĨNH: {self._format_currency(line.net_salary)}', size=13, bold=True, gap=22)

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    @api.model
    def cron_send_salary_notifications(self):
        today = fields.Date.today()
        periods = self.search([
            ('state', '=', 'confirmed'),
            ('notification_auto_send', '=', True),
            ('notification_date', '!=', False),
            ('notification_date', '<=', today),
            ('notification_status', '!=', 'sent'),
        ])
        periods.action_send_salary_notifications()


class PayrollEmployeeLine(models.Model):
    _name = 'payroll.employee.line'
    _description = 'Dòng bảng lương nhân viên'
    _order = 'net_salary desc, id asc'
    _rec_name = 'nhan_vien_id'

    period_id = fields.Many2one('payroll.period', string='Kỳ lương', required=True, ondelete='cascade')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    chuc_vu_id = fields.Many2one('chuc_vu', string='Chức vụ', readonly=True)
    position_rule_id = fields.Many2one('payroll.position.rule', string='Quy tắc lương', readonly=True)
    standard_work_days = fields.Float(string='Công chuẩn tháng', readonly=True)
    payable_work_days = fields.Float(string='Công hưởng lương', readonly=True)
    deducted_work_days = fields.Float(string='Công bị trừ', readonly=True)
    present_days = fields.Float(string='Ngày công đủ', readonly=True)
    absent_days = fields.Float(string='Ngày vắng', readonly=True)
    incomplete_days = fields.Float(string='Ngày thiếu dữ liệu', readonly=True)
    total_minutes_late = fields.Integer(string='Tổng phút đi muộn', readonly=True)
    total_minutes_early = fields.Integer(string='Tổng phút về sớm', readonly=True)
    base_salary = fields.Float(string='Lương cơ bản tháng', readonly=True)
    salary_amount = fields.Float(string='Lương theo công', readonly=True)
    bonus_amount = fields.Float(string='Thưởng chức vụ', readonly=True)
    penalty_amount = fields.Float(string='Tổng phạt', readonly=True)
    net_salary = fields.Float(string='Thực lĩnh', readonly=True)
    notification_status = fields.Selection(
        [('pending', 'Chưa gửi'), ('sent', 'Đã gửi'), ('failed', 'Lỗi gửi')],
        string='Trạng thái gửi',
        default='pending',
        copy=False,
        readonly=True,
    )
    notification_sent_at = fields.Datetime(string='Thời điểm gửi', copy=False, readonly=True)
    notification_error = fields.Text(string='Lỗi gửi thông báo', copy=False, readonly=True)

    _sql_constraints = [
        ('payroll_employee_line_unique', 'unique(period_id, nhan_vien_id)', 'Nhân viên đã có dòng lương trong kỳ này.'),
    ]