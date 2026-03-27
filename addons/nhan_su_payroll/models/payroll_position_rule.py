from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PayrollPositionRule(models.Model):
    _name = 'payroll.position.rule'
    _description = 'Quy tắc lương theo chức vụ'
    _rec_name = 'chuc_vu_id'
    _order = 'chuc_vu_id'

    chuc_vu_id = fields.Many2one('chuc_vu', string='Chức vụ', required=True, ondelete='cascade')
    base_salary = fields.Float(string='Lương cơ bản tháng', required=True, default=0.0)
    bonus_amount = fields.Float(string='Thưởng chức vụ', default=0.0)
    standard_work_days = fields.Float(string='Công chuẩn tháng', required=True, default=26.0)
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(string='Đang áp dụng', default=True)

    _sql_constraints = [
        ('payroll_position_rule_unique', 'unique(chuc_vu_id)', 'Mỗi chức vụ chỉ có một quy tắc lương.'),
    ]

    @api.constrains('base_salary', 'bonus_amount', 'standard_work_days')
    def _check_positive_values(self):
        for record in self:
            if record.base_salary < 0 or record.bonus_amount < 0:
                raise ValidationError('Lương cơ bản và thưởng chức vụ không được âm.')
            if record.standard_work_days <= 0:
                raise ValidationError('Công chuẩn tháng phải lớn hơn 0.')