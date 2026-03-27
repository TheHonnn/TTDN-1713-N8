# -*- coding: utf-8 -*-
"""
Model Extension: HR Attendance
Extend hr.attendance với thông tin từ AI recognition
"""

import logging

from odoo import fields, models
from datetime import timezone
from zoneinfo import ZoneInfo


_logger = logging.getLogger(__name__)


class HRAttendanceExtend(models.Model):
    _inherit = 'hr.attendance'
    
    # ════════════════════════════════════════════════════════════════════════
    # EXTRA FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    # Recognition Info
    is_face_recognition = fields.Boolean(
        'Face Recognition',
        default=False,
        help='Check-in/out via face recognition'
    )
    
    face_confidence = fields.Float(
        'Face Confidence',
        help='Confidence score from AI (0-1)'
    )
    
    # Status
    is_late = fields.Boolean(
        'Is Late',
        compute='_compute_attendance_status',
        store=True,
        help='Đi muộn'
    )
    
    is_early = fields.Boolean(
        'Is Early',
        compute='_compute_attendance_status',
        store=True,
        help='Về sớm'
    )
    
    worked_hours = fields.Float(
        'Worked Hours',
        compute='_compute_worked_hours',
        store=True,
        help='Tổng giờ làm việc'
    )
    
    # Reference
    ai_event_id = fields.Many2one(
        'ai.attendance.event',
        'AI Event',
        readonly=True,
        help='Reference to ai.attendance.event'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # COMPUTE FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    def _compute_attendance_status(self):
        """Compute late/early status"""
        for record in self:
            record.is_late = record.ai_event_id.is_late if record.ai_event_id else False
            record.is_early = record.ai_event_id.is_early if record.ai_event_id else False
    
    def _compute_worked_hours(self):
        """Compute worked hours"""
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.worked_hours = delta.total_seconds() / 3600  # Convert to hours
            else:
                record.worked_hours = 0

    @staticmethod
    def _resolve_timezone_name(record):
        config_tz = record.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        return config_tz or 'Asia/Saigon'

    @classmethod
    def _get_attendance_work_date(cls, record):
        """Return the business date represented by an attendance record."""
        timestamp = record.check_in or record.check_out
        if not timestamp:
            return False

        timezone_name = cls._resolve_timezone_name(record)
        local_tz = ZoneInfo(timezone_name)
        local_timestamp = timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz)
        return local_timestamp.date()

    def _refresh_daily_sheets(self):
        """Update or create daily sheets affected by attendance changes."""
        policy_service = self.env['attendance.policy.service'].sudo()
        for record in self:
            work_date = self._get_attendance_work_date(record)
            if record.employee_id and work_date:
                try:
                    policy_service.generate_daily_sheet(record.employee_id.id, work_date)
                except Exception:
                    _logger.exception('Failed to refresh daily sheet for attendance %s', record.id)

    @models.api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_daily_sheets()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._refresh_daily_sheets()
        return result
