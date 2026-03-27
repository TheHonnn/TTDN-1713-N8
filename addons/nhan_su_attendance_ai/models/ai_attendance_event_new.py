# -*- coding: utf-8 -*-
"""
Model: AI Attendance Event
Lưu lại toàn bộ sự kiện chấm công từ AI recognition
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)


class AIAttendanceEvent(models.Model):
    _name = 'ai.attendance.event'
    _description = 'Sự kiện chấm công AI'
    _order = 'timestamp desc'
    
    # ════════════════════════════════════════════════════════════════════════
    # FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    # Employee
    employee_id = fields.Many2one(
        'hr.employee',
        'Nhân viên',
        required=True,
        index=True,
        ondelete='cascade'
    )

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        'Nhân viên QLNS',
        index=True,
        ondelete='set null'
    )
    
    employee_code = fields.Char(
        'Mã nhân viên',
        compute='_compute_employee_code',
        store=True,
        readonly=True
    )
    
    # Timing
    timestamp = fields.Datetime(
        'Thời điểm chấm công',
        required=True,
        index=True
    )
    
    check_type = fields.Selection(
        [
            ('check_in', 'Chấm công vào'),
            ('check_out', 'Chấm công ra'),
        ],
        'Loại chấm công',
        required=True,
        default='check_in'
    )
    
    # Recognition Data
    confidence = fields.Float(
        'Điểm tin cậy',
        required=True,
        help='Độ tin cậy nhận diện khuôn mặt (0-1)'
    )
    
    distance = fields.Float(
        'Khoảng cách khuôn mặt',
        help='Khoảng cách Euclidean từ vector tham chiếu'
    )
    
    # Status
    status = fields.Selection(
        [
            ('pending', 'Chờ xử lý'),
            ('success', 'Thành công'),
            ('low_confidence', 'Độ tin cậy thấp'),
            ('no_match', 'Không khớp'),
            ('duplicate', 'Trùng lặp'),
            ('error', 'Lỗi'),
        ],
        'Trạng thái nhận diện',
        default='pending',
        readonly=True
    )
    
    is_late = fields.Boolean(
        'Đi muộn',
        compute='_compute_is_late',
        store=True
    )
    
    is_early = fields.Boolean(
        'Về sớm',
        compute='_compute_is_early',
        store=True
    )
    
    # HR Reference
    attendance_id = fields.Many2one(
        'hr.attendance',
        'Chấm công nhân sự',
        readonly=True,
        help='Liên kết đến hr.attendance sau khi xử lý'
    )
    
    # Metadata
    camera_source = fields.Char(
        'Nguồn camera',
        help='Camera hoặc địa điểm gửi dữ liệu'
    )
    
    image_base64 = fields.Binary(
        'Ảnh khuôn mặt',
        help='Ảnh khuôn mặt mã hóa base64'
    )
    
    is_flagged = fields.Boolean(
        'Đánh dấu để xem xét',
        default=False
    )
    
    flag_reason = fields.Text(
        'Lý do đánh dấu',
        help='Lý do cần xem xét thủ công'
    )
    
    notes = fields.Text('Ghi chú')
    
    request_id = fields.Char(
        'ID Yêu cầu',
        index=True,
        help='Tham chiếu đến ai.request.log'
    )
    
    created_at = fields.Datetime(
        'Ngày tạo',
        default=lambda self: datetime.now(),
        readonly=True
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # COMPUTE FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    @api.depends('timestamp', 'employee_id')
    def _compute_check_type(self):
        """Xác định check_in/check_out dựa theo trạng thái thực tế trong ngày"""
        for record in self:
            if not record.timestamp or not record.employee_id:
                record.check_type = 'check_in'
                continue

            # Dùng AttendanceLogicService để xác định
            service = self.env['attendance.logic.service']
            timezone_name = record._resolve_timezone_name()
            record.check_type = service._determine_check_type(
                record.employee_id, record.timestamp, timezone_name
            )

    @api.depends(
        'nhan_vien_id',
        'nhan_vien_id.ma_dinh_danh',
        'employee_id',
        'employee_id.barcode',
        'employee_id.identification_id',
        'employee_id.name'
    )
    def _compute_employee_code(self):
        for record in self:
            if record.nhan_vien_id:
                record.employee_code = record.nhan_vien_id.ma_dinh_danh or record.nhan_vien_id.ho_va_ten or False
                continue
            employee = record.employee_id
            record.employee_code = employee.barcode or employee.identification_id or employee.name or False
    
    @api.depends('timestamp', 'check_type')
    def _compute_is_late(self):
        """Kiểm tra xem có đi muộn không"""
        for record in self:
            record.is_late = False
            
            if record.check_type != 'check_in':
                continue
            
            # Mặc định: check-in sau 8:30 tính là muộn
            check_time = record._to_local_datetime(record.timestamp).time()
            late_time = datetime.strptime('08:30', '%H:%M').time()
            
            if check_time > late_time:
                record.is_late = True
    
    @api.depends('timestamp', 'check_type')
    def _compute_is_early(self):
        """Kiểm tra xem có về sớm không"""
        for record in self:
            record.is_early = False
            
            if record.check_type != 'check_out':
                continue
            
            # Mặc định: check-out trước 17:00 tính là về sớm
            check_time = record._to_local_datetime(record.timestamp).time()
            early_time = datetime.strptime('17:00', '%H:%M').time()
            
            if check_time < early_time:
                record.is_early = True
    
    # ════════════════════════════════════════════════════════════════════════
    # METHODS
    # ════════════════════════════════════════════════════════════════════════
    
    def sync_to_hr_attendance(self):
        """
        Sync this event to hr.attendance
        Được gọi từ AttendanceLogicService
        """
        for record in self:
            if record.attendance_id:
                # Already synced
                continue
            
            # Find or create hr.attendance
            attendance = self.env['hr.attendance'].search(
                [
                    ('employee_id', '=', record.employee_id.id),
                    ('check_in', '=', record.timestamp),
                ],
                limit=1
            )
            
            if not attendance:
                # Create new
                if record.check_type == 'check_in':
                    attendance = self.env['hr.attendance'].create({
                        'employee_id': record.employee_id.id,
                        'check_in': record.timestamp,
                    })
                else:
                    # Find corresponding check-in
                    day_start, _day_end = record._get_local_day_bounds(record.timestamp)
                    checkin = self.env['hr.attendance'].search(
                        [
                            ('employee_id', '=', record.employee_id.id),
                            ('check_in', '>=', day_start),
                            ('check_out', '=', False),
                        ],
                        order='check_in desc',
                        limit=1
                    )
                    
                    if checkin:
                        checkin.write({'check_out': record.timestamp})
                        attendance = checkin
            else:
                # Update if check-out
                if record.check_type == 'check_out' and not attendance.check_out:
                    attendance.write({'check_out': record.timestamp})
            
            if attendance:
                record.attendance_id = attendance.id
    
    def flag_for_review(self, reason):
        """Flag record để review thủ công"""
        self.write({
            'is_flagged': True,
            'flag_reason': reason,
        })
        _logger.info(f"Flagged {self.id} for review: {reason}")
    
    @api.model
    def cleanup_old_records(self, days=90):
        """Xoá records cũ hơn N ngày (optional)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        old_records = self.search([
            ('created_at', '<', cutoff_date)
        ])
        old_records.unlink()
        _logger.info(f"Cleaned up {len(old_records)} old records")

    def _resolve_timezone_name(self):
        self.ensure_one()
        config_tz = self.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        return config_tz or 'Asia/Saigon'

    def _to_local_datetime(self, timestamp):
        self.ensure_one()
        local_tz = ZoneInfo(self._resolve_timezone_name())
        if timestamp.tzinfo:
            return timestamp.astimezone(local_tz).replace(tzinfo=None)
        return timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)

    def _get_local_day_bounds(self, timestamp):
        self.ensure_one()
        local_tz = ZoneInfo(self._resolve_timezone_name())
        local_timestamp = self._to_local_datetime(timestamp)
        local_start = local_timestamp.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz)
        local_end = local_start + timedelta(days=1)
        return (
            local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None),
        )
