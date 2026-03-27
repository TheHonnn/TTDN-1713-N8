# -*- coding: utf-8 -*-
"""
Model: Daily Sheet
Bảng công theo ngày cho mỗi nhân viên
"""

from odoo import models, fields, api
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class DailySheet(models.Model):
    _name = 'daily.sheet'
    _description = 'Bảng công theo ngày'
    _rec_name = 'nhan_vien_id'
    
    # ════════════════════════════════════════════════════════════════════════
    # KEY FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    employee_id = fields.Many2one(
        'hr.employee',
        'Nhân viên',
        required=True,
        ondelete='cascade',
        index=True
    )

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        'Nhân viên QLNS',
        index=True,
        help='Nhân viên nguồn trong module nhan_su dùng để hiển thị bảng công.'
    )
    
    work_date = fields.Date(
        'Ngày làm việc',
        required=True,
        index=True,
        default=fields.Date.context_today
    )
    
    shift_id = fields.Many2one(
        'attendance.rule',
        'Ca làm việc',
        required=True,
        help='Ca làm việc được áp dụng cho ngày này'
    )

    holiday_id = fields.Many2one(
        'attendance.holiday',
        'Ngày nghỉ chuẩn',
        compute='_compute_policy_status',
        store=True,
        readonly=True,
    )

    exception_request_id = fields.Many2one(
        'attendance.exception.request',
        'Đơn ngoại lệ',
        compute='_compute_policy_status',
        store=True,
        readonly=True,
    )

    day_type = fields.Selection(
        [
            ('regular', 'Ngày làm việc'),
            ('weekend', 'Cuối tuần'),
            ('holiday', 'Ngày lễ / lịch nghỉ'),
            ('leave', 'Nghỉ phép hợp lệ'),
        ],
        'Loại ngày',
        compute='_compute_policy_status',
        store=True,
        default='regular',
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # ATTENDANCE DATA
    # ════════════════════════════════════════════════════════════════════════
    
    check_in = fields.Datetime(
        'Giờ vào',
        readonly=True,
        help='Lần ghi nhận vào ca đầu tiên từ hệ thống chấm công'
    )
    
    check_out = fields.Datetime(
        'Giờ ra',
        readonly=True,
        help='Lần ghi nhận ra ca cuối cùng từ hệ thống chấm công'
    )
    
    hours_worked = fields.Float(
        'Tổng giờ làm',
        compute='_compute_hours_worked',
        store=True,
        help='Tổng số giờ làm việc giữa giờ vào và giờ ra'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # POLICY CALCULATIONS
    # ════════════════════════════════════════════════════════════════════════
    
    is_late = fields.Boolean(
        'Đi muộn',
        compute='_compute_policy_status',
        store=True
    )
    
    minutes_late = fields.Integer(
        'Số phút đi muộn',
        compute='_compute_policy_status',
        store=True,
        help='Số phút đi muộn sau thời gian cho phép'
    )
    
    is_early = fields.Boolean(
        'Về sớm',
        compute='_compute_policy_status',
        store=True,
        help='Rời ca sớm hơn thời gian cho phép'
    )
    
    minutes_early = fields.Integer(
        'Số phút về sớm',
        compute='_compute_policy_status',
        store=True,
        help='Số phút về sớm trước thời gian cho phép'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # STATUS
    # ════════════════════════════════════════════════════════════════════════
    
    status = fields.Selection(
        [
            ('present', 'Có mặt'),
            ('absent', 'Vắng mặt'),
            ('incomplete', 'Thiếu dữ liệu (chưa có giờ ra)'),
            ('on_leave', 'Nghỉ phép'),
            ('holiday', 'Ngày nghỉ'),
        ],
        'Trạng thái',
        compute='_compute_policy_status',
        store=True,
        default='absent'
    )
    
    notes = fields.Text(
        'Ghi chú',
        compute='_compute_policy_status',
        store=True,
        help='Tóm tắt tình trạng đi muộn, về sớm hoặc vắng mặt'
    )

    is_exception_approved = fields.Boolean(
        'Có ngoại lệ hợp lệ',
        compute='_compute_policy_status',
        store=True,
    )

    base_work_day = fields.Float(
        'Công gốc',
        compute='_compute_policy_status',
        store=True,
        help='Công gốc theo trạng thái ngày công trước khi trừ bậc vi phạm.'
    )

    deduction_work_day = fields.Float(
        'Công bị trừ',
        compute='_compute_policy_status',
        store=True,
        help='Tổng số công bị trừ theo bậc đi muộn và về sớm.'
    )

    payable_work_day = fields.Float(
        'Công được hưởng',
        compute='_compute_policy_status',
        store=True,
        help='Số công cuối cùng được dùng để tính lương.'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    @api.depends('check_in', 'check_out')
    def _compute_hours_worked(self):
        """Calculate total hours worked"""
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.hours_worked = delta.total_seconds() / 3600
            else:
                record.hours_worked = 0
    
    @api.depends('check_in', 'check_out', 'shift_id', 'work_date', 'employee_id', 'nhan_vien_id')
    def _compute_policy_status(self):
        """Compute policy status based on shift rules"""
        for record in self:
            holiday = record._get_holiday_record()
            exception_request = record._get_exception_request()
            note_parts = []

            record.holiday_id = holiday.id if holiday else False
            record.exception_request_id = exception_request.id if exception_request else False
            record.is_exception_approved = bool(exception_request)

            if not record.shift_id:
                record.status = 'absent'
                record.day_type = 'regular'
                record.notes = 'Chưa được gán ca làm việc'
                record.is_late = False
                record.minutes_late = 0
                record.is_early = False
                record.minutes_early = 0
                record.base_work_day = 0.0
                record.deduction_work_day = 0.0
                record.payable_work_day = 0.0
                continue

            is_weekend = not record.shift_id.is_scheduled_workday(record.work_date)
            if holiday:
                record.day_type = 'holiday'
                note_parts.append(holiday.name)
            elif is_weekend:
                record.day_type = 'weekend'
                note_parts.append('Cuối tuần theo lịch chuẩn')
            else:
                record.day_type = 'regular'

            if not record.check_in:
                if exception_request and exception_request.justify_absence:
                    record.status = 'on_leave'
                    record.day_type = 'leave'
                    record.notes = 'Nghỉ phép hợp lệ' if exception_request.is_paid_leave else 'Nghỉ phép không tính công'
                    record.is_late = False
                    record.minutes_late = 0
                    record.is_early = False
                    record.minutes_early = 0
                    record.base_work_day = 1.0 if exception_request.is_paid_leave else 0.0
                    record.deduction_work_day = 0.0
                    record.payable_work_day = record.base_work_day
                    continue

                if holiday or is_weekend:
                    record.status = 'holiday'
                    record.notes = ', '.join(note_parts) if note_parts else 'Ngày nghỉ'
                    record.is_late = False
                    record.minutes_late = 0
                    record.is_early = False
                    record.minutes_early = 0
                    record.base_work_day = 0.0
                    record.deduction_work_day = 0.0
                    record.payable_work_day = 0.0
                    continue

                record.status = 'absent'
                record.notes = 'Chưa có giờ vào'
                record.is_late = False
                record.minutes_late = 0
                record.is_early = False
                record.minutes_early = 0
                record.base_work_day = 0.0
                record.deduction_work_day = 0.0
                record.payable_work_day = 0.0
                continue
            
            # Calculate shift times for the work date
            shift_start_time = record.shift_id.start_time
            shift_end_time = record.shift_id.end_time
            
            # Convert float hours to time (e.g., 8.5 = 08:30)
            shift_start_hour = int(shift_start_time)
            shift_start_min = int((shift_start_time - shift_start_hour) * 60)
            shift_end_hour = int(shift_end_time)
            shift_end_min = int((shift_end_time - shift_end_hour) * 60)
            
            shift_start = datetime.combine(
                record.work_date,
                datetime.min.time()
            ).replace(hour=shift_start_hour, minute=shift_start_min)
            
            shift_end = datetime.combine(
                record.work_date,
                datetime.min.time()
            ).replace(hour=shift_end_hour, minute=shift_end_min)

            local_check_in = record._to_local_datetime(record.check_in)
            local_check_out = record._to_local_datetime(record.check_out)
            
            # Check for late arrival
            allowed_late = timedelta(minutes=record.shift_id.allow_late_minutes or 0)
            late_justified = bool(exception_request and exception_request.justify_late)
            record.is_late = local_check_in > (shift_start + allowed_late) and not late_justified
            record.minutes_late = int((local_check_in - shift_start).total_seconds() / 60) if record.is_late else 0
            
            # Check for early departure
            if record.is_late:
                note_parts.append(f'Đi muộn {record.minutes_late} phút')
            elif late_justified and local_check_in > shift_start:
                note_parts.append('Đi muộn đã được hợp thức hóa')
            
            if local_check_out:
                allowed_early = timedelta(minutes=record.shift_id.allow_early_minutes or 0)
                early_justified = bool(exception_request and exception_request.justify_early)
                record.is_early = local_check_out < (shift_end - allowed_early) and not early_justified
                record.minutes_early = int((shift_end - local_check_out).total_seconds() / 60) if record.is_early else 0
                record.status = 'present'
                record.base_work_day = 1.0
                
                if record.is_early:
                    note_parts.append(f'Về sớm {record.minutes_early} phút')
                elif early_justified and local_check_out < shift_end:
                    note_parts.append('Về sớm đã được hợp thức hóa')
            else:
                record.status = 'incomplete'
                record.minutes_early = 0
                record.is_early = False
                record.base_work_day = 0.5
                note_parts.append('Chưa có giờ ra')

            late_deduction = record.shift_id.get_workday_deduction('late', record.minutes_late)
            early_deduction = record.shift_id.get_workday_deduction('early', record.minutes_early)
            total_deduction = min(record.base_work_day, late_deduction + early_deduction)
            record.deduction_work_day = total_deduction
            record.payable_work_day = max(record.base_work_day - total_deduction, 0.0)

            if total_deduction:
                note_parts.append(f'Trừ {total_deduction} công theo bậc vi phạm')

            record.notes = ', '.join(note_parts) if note_parts else 'Bình thường'

    def _get_holiday_record(self):
        self.ensure_one()
        return self.env['attendance.holiday'].sudo().search([
            ('active', '=', True),
            ('date_start', '<=', self.work_date),
            ('date_end', '>=', self.work_date),
        ], limit=1)

    def _get_exception_request(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'approved'),
            ('request_date', '=', self.work_date),
        ]
        if self.nhan_vien_id:
            domain.append(('nhan_vien_id', '=', self.nhan_vien_id.id))
        elif self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        else:
            return self.env['attendance.exception.request']
        return self.env['attendance.exception.request'].sudo().search(domain, order='id desc', limit=1)

    def _resolve_timezone_name(self):
        self.ensure_one()
        config_tz = self.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        return config_tz or 'Asia/Saigon'

    def _to_local_datetime(self, timestamp):
        self.ensure_one()
        if not timestamp:
            return False
        local_tz = ZoneInfo(self._resolve_timezone_name())
        if timestamp.tzinfo:
            return timestamp.astimezone(local_tz).replace(tzinfo=None)
        return timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)
    
    # ════════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ════════════════════════════════════════════════════════════════════════
    
    _sql_constraints = [
        ('daily_sheet_unique', 'UNIQUE(employee_id, work_date)',
            'Đã tồn tại bảng công của nhân viên này trong ngày đã chọn'),
    ]
    
    # ════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ════════════════════════════════════════════════════════════════════════
    
    def action_generate_sheet(self):
        """Regenerate this daily sheet by calling policy service"""
        policy_service = self.env['attendance.policy.service']
        
        for record in self:
            # Delete current sheet
            record.unlink()
            
            # Generate new one
            policy_service.generate_daily_sheet(
                record.employee_id.id,
                record.work_date
            )