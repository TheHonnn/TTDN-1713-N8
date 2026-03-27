# -*- coding: utf-8 -*-
"""
Model: Attendance Rule (Luật công ty)
Định nghĩa ca làm việc, cho phép giờ công
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AttendanceRule(models.Model):
    _name = 'attendance.rule'
    _description = 'Ca làm việc / Quy tắc chấm công'
    _rec_name = 'shift_name'
    
    # ════════════════════════════════════════════════════════════════════════
    # BASIC INFO
    # ════════════════════════════════════════════════════════════════════════
    
    shift_name = fields.Char(
        'Tên ca',
        required=True,
        help='Ví dụ: Ca sáng, Ca hành chính 8:30-17:00, Ca tối'
    )
    
    description = fields.Text('Mô tả')

    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    
    is_default = fields.Boolean(
        'Ca mặc định',
        default=False,
        help='Dùng ca này khi nhân viên chưa được gán ca cụ thể'
    )
    
    active = fields.Boolean(
        'Đang áp dụng',
        default=True
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # WORK HOURS
    # ════════════════════════════════════════════════════════════════════════
    
    start_time = fields.Float(
        'Giờ vào ca',
        required=True,
        help='Dùng định dạng 24 giờ, ví dụ 8.5 là 8:30, 6 là 6:00'
    )
    
    end_time = fields.Float(
        'Giờ tan ca',
        required=True,
        help='Dùng định dạng 24 giờ, ví dụ 17 là 17:00, 22.5 là 22:30'
    )
    
    break_duration = fields.Float(
        'Thời gian nghỉ (giờ)',
        default=1.0,
        help='Thời gian nghỉ sẽ được trừ khỏi tổng giờ làm việc'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # ALLOWANCES
    # ════════════════════════════════════════════════════════════════════════
    
    allow_late_minutes = fields.Integer(
        'Cho phép đi muộn (phút)',
        default=0,
        help='Số phút đi muộn được chấp nhận mà không tính vi phạm'
    )
    
    allow_early_minutes = fields.Integer(
        'Cho phép về sớm (phút)',
        default=0,
        help='Số phút về sớm được chấp nhận mà không tính vi phạm'
    )

    monday_work = fields.Boolean('Làm thứ 2', default=True)
    tuesday_work = fields.Boolean('Làm thứ 3', default=True)
    wednesday_work = fields.Boolean('Làm thứ 4', default=True)
    thursday_work = fields.Boolean('Làm thứ 5', default=True)
    friday_work = fields.Boolean('Làm thứ 6', default=True)
    saturday_work = fields.Boolean('Làm thứ 7', default=False)
    sunday_work = fields.Boolean('Làm chủ nhật', default=False)

    penalty_line_ids = fields.One2many(
        'attendance.rule.penalty',
        'rule_id',
        string='Bậc trừ công'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # NOTES
    # ════════════════════════════════════════════════════════════════════════
    
    notes = fields.Text('Ghi chú')
    
    # ════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    daily_hours = fields.Float(
        'Số giờ làm việc chuẩn',
        compute='_compute_daily_hours',
        store=True,
        help='Tổng số giờ làm việc trong ngày sau khi trừ thời gian nghỉ'
    )
    
    @api.depends('start_time', 'end_time', 'break_duration')
    def _compute_daily_hours(self):
        """Calculate total daily hours"""
        for record in self:
            record.daily_hours = record.end_time - record.start_time - record.break_duration

    @api.constrains('start_time', 'end_time')
    def _check_shift_time(self):
        for record in self:
            if record.end_time <= record.start_time:
                raise ValidationError('Giờ tan ca phải lớn hơn giờ vào ca.')

    @api.constrains('is_default', 'company_id', 'active')
    def _check_single_default_per_company(self):
        for record in self.filtered(lambda r: r.is_default and r.active):
            duplicate = self.search([
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('is_default', '=', True),
                ('active', '=', True),
            ], limit=1)
            if duplicate:
                raise ValidationError('Mỗi công ty chỉ được có 1 ca mặc định đang áp dụng.')

    def is_scheduled_workday(self, work_date):
        self.ensure_one()
        weekday_map = {
            0: self.monday_work,
            1: self.tuesday_work,
            2: self.wednesday_work,
            3: self.thursday_work,
            4: self.friday_work,
            5: self.saturday_work,
            6: self.sunday_work,
        }
        return weekday_map.get(work_date.weekday(), False)

    def get_workday_deduction(self, violation_type, minutes_value):
        self.ensure_one()
        if not minutes_value or minutes_value <= 0:
            return 0.0

        matching_line = self.penalty_line_ids.filtered(
            lambda line: line.violation_type == violation_type
            and line.min_minutes <= minutes_value
            and (not line.max_minutes or minutes_value <= line.max_minutes)
        )
        if not matching_line:
            return 0.0
        return matching_line.sorted(key=lambda line: line.min_minutes, reverse=True)[0].deduct_work_day