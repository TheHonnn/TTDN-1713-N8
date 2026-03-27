# -*- coding: utf-8 -*-

from odoo import fields, models


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên QLNS',
        index=True,
        ondelete='set null',
        help='Bản ghi nhân viên nguồn trong module nhan_su.',
    )

    shift_id = fields.Many2one(
        'attendance.rule',
        string='Ca làm việc',
        domain="[('active', '=', True), ('company_id', '=', company_id)]",
        help='Ca làm việc mặc định được áp dụng khi tính bảng công cho nhân viên này.'
    )