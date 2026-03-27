from odoo import fields, models


class NhanVien(models.Model):
    _inherit = 'nhan_vien'

    shift_id = fields.Many2one(
        'attendance.rule',
        string='Ca làm việc',
        domain="[('active', '=', True), ('company_id', '=', company_id)]",
        help='Ca làm việc áp dụng cho nhân viên trong module QLNS.',
    )