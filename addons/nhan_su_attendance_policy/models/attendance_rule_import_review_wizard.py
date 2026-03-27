# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class AttendanceRuleImportReviewPenalty(models.TransientModel):
    _name = 'attendance.rule.import.review.penalty'
    _description = 'Bậc phạt review trước khi áp dụng'
    _order = 'violation_type, min_minutes'

    wizard_id = fields.Many2one(
        'attendance.rule.import.review.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    violation_type = fields.Selection(
        [('late', 'Đi muộn'), ('early', 'Về sớm')],
        string='Loại vi phạm',
        required=True,
        default='late',
    )
    min_minutes = fields.Integer(string='Từ phút', required=True, default=0)
    max_minutes = fields.Integer(string='Đến phút (0 = không giới hạn)', default=0)
    deduct_work_day = fields.Float(string='Trừ công (ngày)', required=True, default=0.0, digits=(4, 2))
    note = fields.Char(string='Ghi chú')


class AttendanceRuleImportReviewWizard(models.TransientModel):
    _name = 'attendance.rule.import.review.wizard'
    _description = 'Xem xét và chỉnh thông tin trước khi áp dụng luật'

    import_record_id = fields.Many2one(
        'attendance.rule.import',
        string='Hồ sơ nhập',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one('res.company', string='Công ty', required=True)
    target_rule_id = fields.Many2one(
        'attendance.rule',
        string='Ca làm việc cần cập nhật',
        domain="[('company_id', '=', company_id)]",
        help='Để trống nếu muốn tạo ca mới.',
    )
    shift_name = fields.Char(string='Tên ca', required=True)
    start_time = fields.Float(string='Giờ vào', required=True)
    end_time = fields.Float(string='Giờ tan ca', required=True)
    break_duration = fields.Float(string='Nghỉ giữa ca (giờ)')
    allow_late_minutes = fields.Integer(string='Cho phép đi muộn (phút)')
    allow_early_minutes = fields.Integer(string='Cho phép về sớm (phút)')
    is_default = fields.Boolean(string='Ca mặc định')

    monday_work = fields.Boolean(string='Thứ 2', default=True)
    tuesday_work = fields.Boolean(string='Thứ 3', default=True)
    wednesday_work = fields.Boolean(string='Thứ 4', default=True)
    thursday_work = fields.Boolean(string='Thứ 5', default=True)
    friday_work = fields.Boolean(string='Thứ 6', default=True)
    saturday_work = fields.Boolean(string='Thứ 7')
    sunday_work = fields.Boolean(string='Chủ nhật')

    notes = fields.Text(string='Ghi chú phạt / nội quy')
    penalty_line_ids = fields.One2many(
        'attendance.rule.import.review.penalty',
        'wizard_id',
        string='Các bậc phạt',
    )

    def action_confirm(self):
        self.ensure_one()
        import_rec = self.import_record_id
        if not import_rec:
            raise UserError('Không tìm thấy hồ sơ nhập.')

        if self.end_time <= self.start_time:
            raise UserError('Giờ tan ca phải lớn hơn giờ vào ca.')

        vals = {
            'company_id': self.company_id.id,
            'shift_name': self.shift_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'break_duration': self.break_duration,
            'allow_late_minutes': self.allow_late_minutes,
            'allow_early_minutes': self.allow_early_minutes,
            'is_default': self.is_default,
            'monday_work': self.monday_work,
            'tuesday_work': self.tuesday_work,
            'wednesday_work': self.wednesday_work,
            'thursday_work': self.thursday_work,
            'friday_work': self.friday_work,
            'saturday_work': self.saturday_work,
            'sunday_work': self.sunday_work,
            'notes': self.notes or False,
        }

        penalty_commands = [(5, 0, 0)]
        for line in self.penalty_line_ids:
            penalty_commands.append((0, 0, {
                'violation_type': line.violation_type,
                'min_minutes': line.min_minutes,
                'max_minutes': line.max_minutes or False,
                'deduct_work_day': line.deduct_work_day,
                'note': line.note or False,
            }))
        vals['penalty_line_ids'] = penalty_commands

        target_rule = self.target_rule_id or import_rec.target_rule_id
        if target_rule:
            target_rule.write(vals)
            rule = target_rule
        else:
            rule = self.env['attendance.rule'].create(vals)

        import_rec.write({
            'applied_rule_id': rule.id,
            'target_rule_id': rule.id,
            'state': 'applied',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Ca làm việc',
            'res_model': 'attendance.rule',
            'view_mode': 'form',
            'res_id': rule.id,
            'target': 'current',
        }
