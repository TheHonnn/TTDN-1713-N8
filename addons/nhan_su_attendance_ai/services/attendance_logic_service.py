# -*- coding: utf-8 -*-
"""
Service: Attendance Logic
Xử lý logic chấm công từ AI events
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)


class AttendanceLogicService(models.AbstractModel):
    """Service layer for attendance processing"""
    
    _name = 'attendance.logic.service'
    _description = 'Attendance Logic Service'
    
    # ════════════════════════════════════════════════════════════════════════
    # MAIN PROCESS (Called by Module 1)
    # ════════════════════════════════════════════════════════════════════════
    
    def process_checkin(self, employee, payload):
        """
        Process checkin from Module 1 API service
        This is the interface that Module 1 calls
        
        Args:
            employee: hr.employee record
            payload (dict): {
                'employee_code': str,
                'timestamp': datetime,
                'confidence': float,
            }
        
        Returns:
            ai.attendance.event record
        """
        try:
            # Step 1: Create ai.attendance.event record
            timestamp = payload.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            timezone_name = self._resolve_timezone_name(employee, payload)
            local_timestamp = payload.get('local_timestamp')
            if isinstance(local_timestamp, str):
                local_timestamp = datetime.fromisoformat(local_timestamp)
            if not isinstance(local_timestamp, datetime):
                local_timestamp = self._to_local_timestamp(timestamp, timezone_name)

            # Xác định vào/ra theo trạng thái thực tế: đã có check-in hôm nay chưa?
            check_type = self._determine_check_type(employee, timestamp, timezone_name)
            
            ai_event = self.env['ai.attendance.event'].sudo().create({
                'employee_id': employee.id,
                'nhan_vien_id': payload.get('nhan_vien_id'),
                'timestamp': timestamp,
                'check_type': check_type,
                'confidence': payload.get('confidence', 0.0),
                'request_id': payload.get('request_id'),
                'camera_source': payload.get('camera_source', 'Unknown'),
                'distance': payload.get('distance', 0.0),
                'status': 'pending',
            })
            
            # Step 2: Process the event (duplicate check, hr.attendance sync)
            process_result = self.process_ai_event(ai_event.id)
            
            if process_result.get('status') != 'error':
                return ai_event
            else:
                # If processing failed, mark event as error
                ai_event.write({'status': 'error'})
                raise UserError(process_result['message'])
        
        except Exception as e:
            _logger.exception('Error in process_checkin')
            raise
    
    def process_ai_event(self, ai_event_id):
        """
        Main method to process an AI attendance event
        
        Args:
            ai_event_id (id): AI attendance event record
            
        Returns:
            dict: Processing result with status, messages
        """
        try:
            ai_event = self.env['ai.attendance.event'].sudo().browse(ai_event_id)
            if not ai_event.exists():
                return self._error_response('Event not found')
            
            # Step 1: Validate event
            validation_result = self._validate_event(ai_event)
            if not validation_result['success']:
                return validation_result
            
            # Step 2: Check for duplicate in hr.attendance
            duplicate_check = self._check_hr_duplicate(ai_event)
            if duplicate_check['is_duplicate']:
                ai_event.write({
                    'status': 'duplicate',
                })
                return self._duplicate_response(duplicate_check)
            
            # Step 3: Find or create corresponding hr.attendance
            hr_attendance_result = self._sync_to_hr_attendance(ai_event)
            if not hr_attendance_result['success']:
                return self._error_response(hr_attendance_result['message'])
            
            # Step 4: Update event status to success
            ai_event.write({
                'status': 'success',
                'attendance_id': hr_attendance_result['attendance_id'],
            })
            
            return self._success_response(ai_event, hr_attendance_result)
            
        except Exception as e:
            _logger.exception('Error processing AI event')
            return self._error_response(str(e))
    
    # ════════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════════════
    
    def _validate_event(self, ai_event):
        """Validate AI event data"""
        if not ai_event.employee_id:
            return self._error_response('Employee not found in event')

        config = self.env['ir.config_parameter'].sudo()
        min_confidence = float(config.get_param('attendance_ai.min_confidence', '0.35'))
        max_distance = float(config.get_param('attendance_ai.max_face_distance', '0.40'))
        distance = ai_event.distance or 0.0

        if ai_event.confidence < min_confidence and (not distance or distance > max_distance):
            return self._error_response(
                f'Face match too weak: confidence={ai_event.confidence:.4f}, distance={distance:.4f}'
            )
        
        if ai_event.status in ['low_confidence', 'no_match']:
            return self._error_response(f'Event has status: {ai_event.status}')
        
        return {'success': True}
    
    # ════════════════════════════════════════════════════════════════════════
    # DUPLICATE CHECKING
    # ════════════════════════════════════════════════════════════════════════
    
    def _check_hr_duplicate(self, ai_event, cooldown_minutes=5):
        """
        Check if duplicate check-in/out exists in hr.attendance
        
        Returns:
            dict: {'is_duplicate': bool, 'message': str, 'existing_id': int/None}
        """
        cutoff_time = ai_event.timestamp - timedelta(minutes=cooldown_minutes)
        
        # Look for attendance records in cooldown window with same employee and check type
        existing = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', ai_event.employee_id.id),
            ('check_in', '>=', cutoff_time) if ai_event.check_type == 'check_in' else ('check_out', '>=', cutoff_time),
        ], limit=1)
        
        if existing:
            return {
                'is_duplicate': True,
                'message': f'Duplicate {ai_event.check_type} within {cooldown_minutes} minutes',
                'existing_id': existing.id,
            }
        
        return {
            'is_duplicate': False,
            'message': 'No duplicate found',
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # HR ATTENDANCE SYNC
    # ════════════════════════════════════════════════════════════════════════
    
    def _sync_to_hr_attendance(self, ai_event):
        """
        Create or find corresponding hr.attendance record
        
        Returns:
            dict: {'success': bool, 'attendance_id': int, 'message': str, 'action': str}
        """
        try:
            timezone_name = self._resolve_timezone_name(ai_event.employee_id)
            local_timestamp = self._to_local_timestamp(ai_event.timestamp, timezone_name)
            today_start, today_end = self._local_day_bounds(local_timestamp, timezone_name)

            # Determine check-in vs check-out
            if ai_event.check_type == 'check_in':
                # Find today's attendance record or create new
                existing = self.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', ai_event.employee_id.id),
                    ('check_in', '>=', today_start),
                    ('check_in', '<', today_end),
                    ('check_out', '=', False),  # Not yet checked out
                ], limit=1)
                
                if existing:
                    # Update existing check-in time if later
                    if ai_event.timestamp > existing.check_in:
                        existing.write({
                            'check_in': ai_event.timestamp,
                            'is_face_recognition': True,
                            'face_confidence': ai_event.confidence,
                        })
                    return {
                        'success': True,
                        'attendance_id': existing.id,
                        'action': 'updated',
                        'message': 'Updated existing check-in',
                    }
                else:
                    # Create new check-in
                    new_record = self.env['hr.attendance'].sudo().create({
                        'employee_id': ai_event.employee_id.id,
                        'check_in': ai_event.timestamp,
                        'is_face_recognition': True,
                        'face_confidence': ai_event.confidence,
                    })
                    return {
                        'success': True,
                        'attendance_id': new_record.id,
                        'action': 'created',
                        'message': 'Created new check-in record',
                    }
            
            else:  # check_out
                # Find today's check-in without check-out
                existing = self.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', ai_event.employee_id.id),
                    ('check_in', '>=', today_start),
                    ('check_in', '<', today_end),
                    ('check_out', '=', False),  # Not yet checked out
                ], limit=1)
                
                if not existing:
                    # No matching check-in found, create check-in+out same time
                    new_record = self.env['hr.attendance'].sudo().create({
                        'employee_id': ai_event.employee_id.id,
                        'check_in': ai_event.timestamp - timedelta(minutes=1),  # Assume 1 min before
                        'check_out': ai_event.timestamp,
                        'is_face_recognition': True,
                        'face_confidence': ai_event.confidence,
                    })
                    return {
                        'success': True,
                        'attendance_id': new_record.id,
                        'action': 'created',
                        'message': 'Created check-in/out pair (no matching check-in found)',
                    }
                else:
                    # Update check-out time
                    existing.write({
                        'check_out': ai_event.timestamp,
                        'is_face_recognition': True,
                        'face_confidence': ai_event.confidence,
                    })
                    return {
                        'success': True,
                        'attendance_id': existing.id,
                        'action': 'updated',
                        'message': 'Updated check-out time',
                    }
        
        except Exception as e:
            _logger.exception('Error syncing to hr.attendance')
            return {
                'success': False,
                'message': f'Failed to sync: {str(e)}',
                'attendance_id': None,
            }
    
    # ════════════════════════════════════════════════════════════════════════
    # RESPONSE BUILDERS
    # ════════════════════════════════════════════════════════════════════════
    
    def _success_response(self, ai_event, sync_result):
        """Build success response"""
        nhan_vien = ai_event.nhan_vien_id or ai_event.employee_id.nhan_vien_id
        return {
            'status': 'success',
            'event_id': ai_event.id,
            'employee_id': nhan_vien.id if nhan_vien else ai_event.employee_id.id,
            'employee_code': nhan_vien.ma_dinh_danh if nhan_vien else ai_event.employee_code,
            'employee_name': nhan_vien.ho_va_ten if nhan_vien else ai_event.employee_id.name,
            'check_type': ai_event.check_type,
            'timestamp': ai_event.timestamp.isoformat(),
            'confidence': ai_event.confidence,
            'is_late': ai_event.is_late,
            'is_early': ai_event.is_early,
            'attendance_id': sync_result['attendance_id'],
            'sync_action': sync_result['action'],
            'message': sync_result['message'],
        }
    
    def _duplicate_response(self, duplicate_check):
        """Build duplicate response"""
        return {
            'status': 'duplicate',
            'message': duplicate_check['message'],
            'existing_attendance_id': duplicate_check.get('existing_id'),
        }
    
    def _error_response(self, message):
        """Build error response"""
        return {
            'status': 'error',
            'message': message,
            'success': False,
        }

    def _determine_check_type(self, employee, timestamp, timezone_name):
        """
        Xác định check_in hay check_out dựa trên trạng thái thực tế trong ngày:
        - Chưa có check-in hôm nay (hoặc đã check-out rồi) → check_in
        - Đã có check-in, chưa có check-out → check_out
        """
        local_timestamp = self._to_local_timestamp(timestamp, timezone_name)
        if not local_timestamp:
            return 'check_in'

        today_start, today_end = self._local_day_bounds(local_timestamp, timezone_name)

        # Tìm bản ghi hr.attendance chưa được check-out trong ngày hôm nay
        open_checkin = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start),
            ('check_in', '<', today_end),
            ('check_out', '=', False),
        ], limit=1)

        if open_checkin:
            # Đã có vào chưa có ra → ghi ra
            return 'check_out'
        else:
            # Chưa có vào (hoặc đã đủ cặp) → ghi vào
            return 'check_in'

    def _resolve_timezone_name(self, employee, payload=None):
        """Resolve business timezone for attendance decisions."""
        config_tz = self.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        if config_tz:
            return config_tz

        return 'Asia/Saigon'

    @staticmethod
    def _localize_datetime(timestamp, timezone_name):
        local_tz = ZoneInfo(timezone_name)
        if timestamp.tzinfo:
            return timestamp.astimezone(local_tz)
        return timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz)

    def _to_local_timestamp(self, timestamp, timezone_name):
        """Convert stored UTC-naive datetimes to local business time."""
        if not timestamp:
            return False
        return self._localize_datetime(timestamp, timezone_name).replace(tzinfo=None)

    def _local_day_bounds(self, local_timestamp, timezone_name):
        """Return UTC-naive bounds for the local calendar day of the timestamp."""
        local_tz = ZoneInfo(timezone_name)
        local_start = local_timestamp.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz)
        local_end = local_start + timedelta(days=1)
        return (
            local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None),
        )
# DONEEEEEEQ