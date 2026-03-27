# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AttendanceExceptionRequest(models.Model):
    _name = 'attendance.exception.request'
    _description = 'Đơn hợp thức hóa chấm công'
    _order = 'request_date desc, id desc'

    name = fields.Char(string='Tên đơn', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Nhân viên kỹ thuật', ondelete='cascade')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    request_date = fields.Date(string='Ngày áp dụng', required=True, default=fields.Date.context_today)
    justify_late = fields.Boolean(string='Hợp thức đi muộn', default=True)
    justify_early = fields.Boolean(string='Hợp thức về sớm')
    justify_absence = fields.Boolean(string='Hợp thức vắng mặt')
    is_paid_leave = fields.Boolean(string='Tính công đủ khi nghỉ', default=False)
    requested_check_in = fields.Float(string='Giờ vào dự kiến', help='Ví dụ 8.5 là 08:30')
    requested_check_out = fields.Float(string='Giờ ra dự kiến', help='Ví dụ 17 là 17:00')
    reason = fields.Text(string='Lý do', required=True)
    state = fields.Selection(
        [('draft', 'Nháp'), ('approved', 'Đã duyệt'), ('rejected', 'Từ chối')],
        string='Trạng thái',
        default='draft',
        required=True,
    )
    approved_by = fields.Many2one('res.users', string='Người duyệt', readonly=True)
    approved_date = fields.Datetime(string='Ngày duyệt', readonly=True)

    @api.depends('nhan_vien_id', 'request_date')
    def _compute_name(self):
        for record in self:
            employee_name = record.nhan_vien_id.ho_va_ten if record.nhan_vien_id else 'Nhân viên'
            if record.request_date:
                record.name = f'Ngoại lệ {employee_name} - {record.request_date.strftime("%d/%m/%Y")}'
            else:
                record.name = f'Ngoại lệ {employee_name}'

    @api.constrains('justify_late', 'justify_early', 'justify_absence')
    def _check_scope(self):
        for record in self:
            if not (record.justify_late or record.justify_early or record.justify_absence):
                raise ValidationError('Phải chọn ít nhất một loại hợp thức hóa.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_employee_link()
        records._refresh_daily_sheets()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_employee_link()
        self._refresh_daily_sheets()
        return result

    def unlink(self):
        affected = [(record.employee_id.id, record.request_date) for record in self if record.employee_id and record.request_date]
        result = super().unlink()
        policy_service = self.env['attendance.policy.service'].sudo()
        for employee_id, request_date in affected:
            policy_service.generate_daily_sheet(employee_id, request_date)
        return result

    def _sync_employee_link(self):
        employee_model = self.env['hr.employee'].sudo()
        for record in self:
            if record.employee_id or not record.nhan_vien_id:
                continue
            employee = employee_model.search([('nhan_vien_id', '=', record.nhan_vien_id.id)], limit=1)
            if employee:
                record.employee_id = employee.id

    def _refresh_daily_sheets(self):
        policy_service = self.env['attendance.policy.service'].sudo()
        for record in self.filtered(lambda item: item.employee_id and item.request_date):
            policy_service.generate_daily_sheet(record.employee_id.id, record.request_date)

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
