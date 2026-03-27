from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PayrollPenaltyRule(models.Model):
    _name = 'payroll.penalty.rule'
    _description = 'Mức phạt chung'
    _rec_name = 'name'

    name = fields.Char(string='Tên cấu hình', required=True, default='Mức phạt chung')
    late_penalty_per_minute = fields.Float(string='Phạt đi muộn / phút', default=0.0)
    early_penalty_per_minute = fields.Float(string='Phạt về sớm / phút', default=0.0)
    absent_penalty_per_day = fields.Float(string='Phạt vắng / ngày', default=0.0)
    incomplete_penalty_per_day = fields.Float(string='Phạt thiếu dữ liệu / ngày', default=0.0)
    active = fields.Boolean(string='Đang áp dụng', default=True)
    note = fields.Text(string='Ghi chú')

    @api.constrains(
        'late_penalty_per_minute',
        'early_penalty_per_minute',
        'absent_penalty_per_day',
        'incomplete_penalty_per_day',
    )
    def _check_non_negative_values(self):
        for record in self:
            values = [
                record.late_penalty_per_minute,
                record.early_penalty_per_minute,
                record.absent_penalty_per_day,
                record.incomplete_penalty_per_day,
            ]
            if any(value < 0 for value in values):
                raise ValidationError('Các mức phạt không được âm.')

    @api.model
    def get_active_rule(self):
        rule = self.search([('active', '=', True)], order='id desc', limit=1)
        if rule:
            return rule
        return self.create({'name': 'Mức phạt chung'})