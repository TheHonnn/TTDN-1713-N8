# -*- coding: utf-8 -*-
"""
Service: AttendanceAIService
Xử lý logic chấm công từ yêu cầu AI
"""

from odoo import models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, timezone
import logging
import uuid
from zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)


class AttendanceAIService(models.AbstractModel):
    _name = 'attendance.ai.service'
    _description = 'Attendance AI Service'
    
    # ════════════════════════════════════════════════════════════════════════
    # MAIN PROCESSING FLOW
    # ════════════════════════════════════════════════════════════════════════
    
    def process_checkin(self, payload):
        """
        Xử lý điểm danh từ AI
        
        Args:
            payload (dict): {
                'employee_code': str,
                'timestamp': datetime,
                'confidence': float (0-1),
            }
        
        Returns:
            dict: {
                'status': 'success' | 'error',
                'log_id': int,
                'attendance_event_id': int,
                'message': str,
                'employee_name': str,
                'check_type': 'check_in' | 'check_out',
                'is_late': bool,
            }
        """
        request_id = str(uuid.uuid4())
        start_time = datetime.now()
        log_data = {
            'request_id': request_id,
            'endpoint': '/api/face_attendance',
            'request_payload': payload,
            'status': 'pending',
        }
        
        try:
            # Step 1: Validate payload
            self._validate_payload(payload)
            # Step 2: Find employee
            nhan_vien, employee = self._find_employee(payload)
            if not nhan_vien:
                employee_ref = payload.get('employee_code') or payload.get('employee_id')
                raise ValidationError(f"Employee {employee_ref} not found")

            payload['timezone'] = self._resolve_timezone_name(employee, payload)
            payload['local_timestamp'] = self._coerce_datetime(payload['timestamp'])
            payload['timestamp'] = self._normalize_timestamp(payload['timestamp'], employee, payload)
            payload['nhan_vien_id'] = nhan_vien.id
            payload['employee_code'] = nhan_vien.ma_dinh_danh
            log_data['employee_code'] = nhan_vien.ma_dinh_danh
            log_data['nhan_vien_id'] = nhan_vien.id
            log_data['employee_id'] = employee.id
            log_data['request_timestamp'] = payload['timestamp']
            
            # Step 3: Check for duplicates
            is_duplicate, last_checkin = self._check_duplicate(
                employee, 
                payload['timestamp']
            )
            if is_duplicate:
                log_data['status'] = 'duplicate'
                log_data['error_message'] = 'Duplicate check-in within 5 minutes'
                result = self._duplicate_response(nhan_vien, employee, last_checkin)
            else:
                # Step 4: Process attendance
                event = self._create_attendance_event(employee, payload)
                log_data['status'] = 'success'
                log_data['attendance_event_id'] = event.id
                result = self._success_response(nhan_vien, employee, event)
            
            log_data['response_payload'] = result
            
        except ValidationError as e:
            log_data['status'] = 'validation_error'
            log_data['error_message'] = str(e)
            result = {
                'status': 'error',
                'code': 'VALIDATION_ERROR',
                'message': str(e),
            }
            log_data['response_payload'] = result
            _logger.warning(f"Validation error: {e}", exc_info=True)
            
        except Exception as e:
            log_data['status'] = 'error'
            log_data['error_message'] = str(e)
            result = {
                'status': 'error',
                'code': 'PROCESSING_ERROR',
                'message': 'Internal server error',
            }
            log_data['response_payload'] = result
            _logger.error(f"Processing error: {e}", exc_info=True)
        
        finally:
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            log_data['processing_time'] = processing_time
            
            # Create log record, but do not let audit logging break the API response.
            try:
                log = self.env['ai.request.log'].sudo().create_log(log_data)
                result['log_id'] = log.id
            except Exception:
                _logger.exception('Failed to create ai.request.log')
        
        return result
    
    # ════════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════════════
    
    def _validate_payload(self, payload):
        """Validate incoming request"""
        required_fields = ['timestamp', 'confidence']
        
        for field in required_fields:
            if field not in payload:
                raise ValidationError(f"Missing required field: {field}")

        if not payload.get('employee_code') and not payload.get('employee_id'):
            raise ValidationError("Missing required field: employee_code or employee_id")
        
        # Validate confidence
        conf = payload.get('confidence')
        if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
            raise ValidationError("Confidence must be between 0 and 1")
        
        # Validate timestamp
        try:
            if isinstance(payload['timestamp'], str):
                datetime.fromisoformat(payload['timestamp'])
        except:
            raise ValidationError("Invalid timestamp format")

    def _coerce_datetime(self, timestamp_value):
        """Parse timestamp strings into datetime values without changing timezone semantics."""
        if isinstance(timestamp_value, str):
            return datetime.fromisoformat(timestamp_value)
        return timestamp_value

    def _normalize_timestamp(self, timestamp_value, employee=None, payload=None):
        """Convert API timestamps to UTC-naive datetimes for Odoo storage."""
        timestamp = self._coerce_datetime(timestamp_value)

        if not isinstance(timestamp, datetime):
            raise ValidationError('Invalid timestamp value')

        if timestamp.tzinfo:
            return timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        timezone_name = self._resolve_timezone_name(employee, payload)
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValidationError(f'Invalid timezone configured: {timezone_name}') from exc

        localized = timestamp.replace(tzinfo=local_tz)
        return localized.astimezone(timezone.utc).replace(tzinfo=None)

    def _resolve_timezone_name(self, employee=None, payload=None):
        """Resolve the timezone used for naive timestamps from API clients."""
        config_tz = self.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        if config_tz:
            return config_tz

        return 'Asia/Saigon'

    def _to_local_display_timestamp(self, timestamp_value, employee=None, payload=None):
        """Format stored UTC timestamps back to the resolved local timezone for API responses."""
        timestamp = self._coerce_datetime(timestamp_value)
        if not timestamp:
            return False

        timezone_name = self._resolve_timezone_name(employee, payload)
        local_tz = ZoneInfo(timezone_name)
        if timestamp.tzinfo:
            localized = timestamp.astimezone(local_tz)
        else:
            localized = timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz)
        return localized.isoformat()
    
    def _find_employee(self, payload):
        """Resolve nhan_vien as the source employee and sync hr.employee on demand."""
        nhan_vien_model = self.env['nhan_vien'].sudo()

        nhan_vien = nhan_vien_model.browse()
        employee_ref = payload.get('employee_id')
        if employee_ref:
            nhan_vien = nhan_vien_model.browse(employee_ref)
            if not nhan_vien.exists():
                nhan_vien = nhan_vien_model.browse()

        if not nhan_vien:
            employee_code = payload.get('employee_code')
            if employee_code:
                nhan_vien = nhan_vien_model.search([
                    ('ma_dinh_danh', '=', str(employee_code)),
                ], limit=1)

        if not nhan_vien:
            return nhan_vien, self.env['hr.employee'].sudo().browse()

        hr_employee = self._get_or_create_hr_employee(nhan_vien)
        return nhan_vien, hr_employee

    def _get_or_create_hr_employee(self, nhan_vien):
        """Create or update a technical hr.employee record for hr.attendance."""
        employee_model = self.env['hr.employee'].sudo()

        employee = employee_model.search([
            ('nhan_vien_id', '=', nhan_vien.id),
        ], limit=1)
        if not employee and nhan_vien.ma_dinh_danh:
            employee = employee_model.search([
                '|',
                ('barcode', '=', nhan_vien.ma_dinh_danh),
                ('identification_id', '=', nhan_vien.ma_dinh_danh),
            ], limit=1)

        values = {
            'name': nhan_vien.ho_va_ten,
            'barcode': nhan_vien.ma_dinh_danh,
            'identification_id': nhan_vien.ma_dinh_danh,
            'work_email': nhan_vien.email,
            'mobile_phone': nhan_vien.so_dien_thoai,
            'company_id': nhan_vien.company_id.id or self.env.company.id,
            'nhan_vien_id': nhan_vien.id,
        }

        if employee:
            employee.write(values)
            return employee

        return employee_model.create(values)
    
    # ════════════════════════════════════════════════════════════════════════
    # DUPLICATE CHECK
    # ════════════════════════════════════════════════════════════════════════
    
    def _check_duplicate(self, employee, timestamp, cooldown_minutes=5):
        """
        Kiểm tra trùng check-in
        
        Args:
            employee: hr.employee record
            timestamp: datetime
            cooldown_minutes: phút để coi là trùng
        
        Returns:
            (is_duplicate, last_event)
        """
        cutoff_time = timestamp - timedelta(minutes=cooldown_minutes)
        
        last_event = self.env['ai.attendance.event'].sudo().search([
            ('employee_id', '=', employee.id),
            ('status', '=', 'success'),
            ('timestamp', '>=', cutoff_time),
            ('timestamp', '<', timestamp),
        ], order='timestamp desc', limit=1)
        
        is_duplicate = bool(last_event)
        return is_duplicate, last_event
    
    # ════════════════════════════════════════════════════════════════════════
    # ATTENDANCE EVENT CREATION
    # ════════════════════════════════════════════════════════════════════════
    
    def _create_attendance_event(self, employee, payload):
        """Tạo attendance event record"""
        # Gọi service từ nhan_su_attendance_ai
        att_logic_service = self.env['attendance.logic.service'].sudo()
        event = att_logic_service.process_checkin(employee, payload)
        return event
    
    # ════════════════════════════════════════════════════════════════════════
    # RESPONSE BUILDERS
    # ════════════════════════════════════════════════════════════════════════
    
    def _success_response(self, nhan_vien, employee, event):
        """Build success response"""
        return {
            'status': 'success',
            'employee_id': nhan_vien.id,
            'employee_code': nhan_vien.ma_dinh_danh,
            'employee_name': nhan_vien.ho_va_ten,
            'event_id': event.id,
            'check_type': event.check_type,
            'timestamp': self._to_local_display_timestamp(event.timestamp, employee),
            'is_late': event.is_late,
            'message': f"Check-{event.check_type} recorded successfully",
        }
    
    def _duplicate_response(self, nhan_vien, employee, last_event):
        """Build duplicate response"""
        return {
            'status': 'warning',
            'code': 'DUPLICATE_CHECKIN',
            'employee_id': nhan_vien.id,
            'employee_code': nhan_vien.ma_dinh_danh,
            'employee_name': nhan_vien.ho_va_ten,
            'last_timestamp': self._to_local_display_timestamp(last_event.timestamp, employee),
            'message': 'Duplicate check-in within 5 minutes, ignored',
        }
