# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AttendanceRulePenalty(models.Model):
    _name = 'attendance.rule.penalty'
    _description = 'Bậc trừ công theo vi phạm'
    _order = 'rule_id, violation_type, min_minutes, id'

    rule_id = fields.Many2one('attendance.rule', string='Ca làm việc', required=True, ondelete='cascade')
    name = fields.Char(string='Tên bậc', compute='_compute_name', store=True)
    violation_type = fields.Selection(
        [('late', 'Đi muộn'), ('early', 'Về sớm')],
        string='Loại vi phạm',
        required=True,
        default='late',
    )
    min_minutes = fields.Integer(string='Từ phút', required=True, default=0)
    max_minutes = fields.Integer(string='Đến phút')
    deduct_work_day = fields.Float(string='Trừ công', required=True, default=0.0)
    note = fields.Char(string='Ghi chú')

    @api.depends('violation_type', 'min_minutes', 'max_minutes', 'deduct_work_day')
    def _compute_name(self):
        label_map = dict(self._fields['violation_type'].selection)
        for record in self:
            range_label = f"{record.min_minutes}+ phút"
            if record.max_minutes:
                range_label = f"{record.min_minutes}-{record.max_minutes} phút"
            record.name = f"{label_map.get(record.violation_type, '')}: {range_label} -> trừ {record.deduct_work_day} công"

    @api.constrains('min_minutes', 'max_minutes', 'deduct_work_day')
    def _check_values(self):
        for record in self:
            if record.min_minutes < 0 or record.deduct_work_day < 0:
                raise ValidationError('Phút và mức trừ công không được âm.')
            if record.max_minutes and record.max_minutes < record.min_minutes:
                raise ValidationError('Đến phút phải lớn hơn hoặc bằng từ phút.')
