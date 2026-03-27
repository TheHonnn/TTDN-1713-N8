# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AttendanceHoliday(models.Model):
    _name = 'attendance.holiday'
    _description = 'Ngày nghỉ chuẩn'
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Tên ngày nghỉ', required=True)
    date_start = fields.Date(string='Từ ngày', required=True)
    date_end = fields.Date(string='Đến ngày', required=True)
    holiday_type = fields.Selection(
        [('public', 'Ngày lễ'), ('company', 'Lịch nghỉ công ty')],
        string='Loại ngày nghỉ',
        required=True,
        default='public',
    )
    active = fields.Boolean(string='Đang áp dụng', default=True)
    note = fields.Text(string='Ghi chú')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end < record.date_start:
                raise ValidationError('Đến ngày phải lớn hơn hoặc bằng từ ngày.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_daily_sheets()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._refresh_daily_sheets()
        return result

    def unlink(self):
        date_ranges = [(record.date_start, record.date_end) for record in self]
        result = super().unlink()
        self._refresh_range_daily_sheets(date_ranges)
        return result

    def _refresh_daily_sheets(self):
        self._refresh_range_daily_sheets([(record.date_start, record.date_end) for record in self if record.date_start and record.date_end])

    def _refresh_range_daily_sheets(self, date_ranges):
        policy_service = self.env['attendance.policy.service'].sudo()
        employees = self.env['hr.employee'].sudo().search([('active', '=', True)])
        for date_start, date_end in date_ranges:
            current_date = date_start
            while current_date <= date_end:
                for employee in employees:
                    policy_service.generate_daily_sheet(employee.id, current_date)
                current_date += timedelta(days=1)
