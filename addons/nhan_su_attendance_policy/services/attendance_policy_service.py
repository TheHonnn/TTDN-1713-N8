# -*- coding: utf-8 -*-
"""
Service: Attendance Policy Service
Xử lý luật công ty về giờ công, đi muộn, về sớm
"""

import logging
from datetime import datetime, timedelta, date, timezone
from odoo import models
from odoo.exceptions import ValidationError
from zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)


class AttendancePolicyService(models.AbstractModel):
    """Service for attendance policy enforcement"""
    
    _name = 'attendance.policy.service'
    _description = 'Attendance Policy Service'
    
    # ════════════════════════════════════════════════════════════════════════
    # DAILY SHEET GENERATION
    # ════════════════════════════════════════════════════════════════════════
    
    def generate_daily_sheet(self, employee_id, work_date):
        """
        Generate daily attendance sheet for employee
        
        Args:
            employee_id (int): hr.employee ID
            work_date (date): Date to generate sheet for
        
        Returns:
            daily.sheet record
        """
        try:
            employee = self.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                raise ValidationError('Employee not found')

            if isinstance(work_date, datetime):
                work_date = work_date.date()
            
            # Find employee's shift rule for this date
            # For now, use default rule or employee's assigned rule
            shift_rule = self._get_employee_shift(employee, work_date)
            if not shift_rule:
                raise ValidationError('No shift rule assigned for this date')
            
            # Check if sheet already exists
            existing_sheet = self.env['daily.sheet'].sudo().search([
                ('employee_id', '=', employee_id),
                ('work_date', '=', work_date),
            ], limit=1)
            
            # Get attendance records for the day
            day_start, day_end = self._get_local_day_bounds(employee, work_date)
            
            attendance_records = self.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee_id),
                '|',
                '&', ('check_in', '>=', day_start), ('check_in', '<=', day_end),
                '&', ('check_out', '>=', day_start), ('check_out', '<=', day_end),
            ])
            
            # Compute policy status
            check_ins = [record.check_in for record in attendance_records if record.check_in]
            check_outs = [record.check_out for record in attendance_records if record.check_out]
            check_in = min(check_ins) if check_ins else None
            check_out = max(check_outs) if check_outs else None
            
            policy_info = self._compute_policy_status(
                shift_rule, check_in, check_out, work_date
            )
            
            values = {
                'employee_id': employee_id,
                'nhan_vien_id': self._find_nhan_vien_record(employee).id,
                'work_date': work_date,
                'shift_id': shift_rule.id,
                'check_in': check_in,
                'check_out': check_out,
            }

            if existing_sheet:
                existing_sheet.sudo().write(values)
                daily_sheet = existing_sheet
            else:
                daily_sheet = self.env['daily.sheet'].sudo().create(values)
            
            return daily_sheet
            
        except Exception as e:
            _logger.exception('Error generating daily sheet')
            raise
    
    # ════════════════════════════════════════════════════════════════════════
    # POLICY CALCULATION
    # ════════════════════════════════════════════════════════════════════════
    
    def _compute_policy_status(self, shift_rule, check_in, check_out, work_date):
        """
        Compute attendance status based on policy
        
        Returns:
            dict with keys: is_late, minutes_late, is_early, minutes_early, 
                           hours_worked, status, notes
        """
        result = {
            'is_late': False,
            'minutes_late': 0,
            'is_early': False,
            'minutes_early': 0,
            'hours_worked': 0,
            'status': 'absent',
            'notes': '',
        }
        
        if not check_in:
            result['status'] = 'absent'
            result['notes'] = 'No check-in record'
            return result

        timezone_name = self._resolve_timezone_name()
        local_check_in = self._to_local_datetime(check_in, timezone_name)
        local_check_out = self._to_local_datetime(check_out, timezone_name) if check_out else None
        
        # Check for late arrival
        shift_start = self._float_hours_to_datetime(work_date, shift_rule.start_time)
        allowed_late_minutes = shift_rule.allow_late_minutes or 0
        
        if local_check_in > shift_start + timedelta(minutes=allowed_late_minutes):
            result['is_late'] = True
            result['minutes_late'] = int((local_check_in - shift_start).total_seconds() / 60)
        
        # Check for early departure
        if local_check_out:
            shift_end = self._float_hours_to_datetime(work_date, shift_rule.end_time)
            allowed_early_minutes = shift_rule.allow_early_minutes or 0
            
            if local_check_out < shift_end - timedelta(minutes=allowed_early_minutes):
                result['is_early'] = True
                result['minutes_early'] = int((shift_end - local_check_out).total_seconds() / 60)
            
            # Calculate hours worked
            result['hours_worked'] = (local_check_out - local_check_in).total_seconds() / 3600
            result['status'] = 'present'
            
        else:
            result['status'] = 'incomplete'
            result['notes'] = 'No check-out record'
        
        # Add late/early indicators to notes
        if result['is_late']:
            result['notes'] += f"Late {result['minutes_late']} min. "
        if result['is_early']:
            result['notes'] += f"Early {result['minutes_early']} min."
        
        return result

    def _float_hours_to_datetime(self, work_date, float_hours):
        """Convert Odoo float hour values such as 8.5 into a datetime on the given date."""
        hours = float(float_hours or 0.0)
        hour = int(hours)
        minute = int(round((hours - hour) * 60))
        if minute == 60:
            hour += 1
            minute = 0
        return datetime.combine(work_date, datetime.min.time()).replace(hour=hour, minute=minute)
    
    # ════════════════════════════════════════════════════════════════════════
    # SHIFT MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════
    
    def _get_employee_shift(self, employee, work_date):
        """
        Get employee's applicable shift for a specific date
        
        Priority order:
        1. Shift assigned on nhan_vien (custom QLNS employee)
        2. Shift assigned on hr.employee
        3. Default shift
        4. First available shift
        """
        nhan_vien = self._find_nhan_vien_record(employee)
        if nhan_vien and nhan_vien.shift_id:
            return nhan_vien.shift_id

        if hasattr(employee, 'shift_id') and employee.shift_id:
            return employee.shift_id
        
        company_id = employee.company_id.id or self.env.company.id

        # Otherwise use company default shift
        default_shift = self.env['attendance.rule'].search([
            ('is_default', '=', True),
            ('company_id', '=', company_id),
            ('active', '=', True),
        ], limit=1)
        
        if not default_shift:
            # Return any active shift in employee company as fallback
            return self.env['attendance.rule'].search([
                ('company_id', '=', company_id),
                ('active', '=', True),
            ], limit=1)
        
        return default_shift

    def get_or_create_hr_employee(self, nhan_vien):
        employee_model = self.env['hr.employee'].sudo()
        employee = employee_model.search([('nhan_vien_id', '=', nhan_vien.id)], limit=1)
        if employee:
            return employee

        values = {
            'name': nhan_vien.ho_va_ten,
            'barcode': nhan_vien.ma_dinh_danh,
            'identification_id': nhan_vien.ma_dinh_danh,
            'work_email': nhan_vien.email,
            'mobile_phone': nhan_vien.so_dien_thoai,
            'company_id': nhan_vien.company_id.id or self.env.company.id,
            'nhan_vien_id': nhan_vien.id,
        }
        return employee_model.create(values)

    def _find_nhan_vien_record(self, employee):
        """Resolve the custom QLNS employee record linked to an hr.employee."""
        nhan_vien_model = self.env['nhan_vien'].sudo()

        if hasattr(employee, 'nhan_vien_id') and employee.nhan_vien_id:
            return employee.nhan_vien_id

        candidate_codes = [
            employee.barcode,
            employee.identification_id,
        ]
        candidate_codes = [code.strip() for code in candidate_codes if code and code.strip()]

        for code in candidate_codes:
            nhan_vien = nhan_vien_model.search([('ma_dinh_danh', '=', code)], limit=1)
            if nhan_vien:
                return nhan_vien

        if employee.name:
            nhan_vien = nhan_vien_model.search([('ho_va_ten', '=', employee.name.strip())], limit=1)
            if nhan_vien:
                return nhan_vien

        return nhan_vien_model.browse()

    def _resolve_timezone_name(self, employee=None):
        config_tz = self.env['ir.config_parameter'].sudo().get_param('attendance_ai.default_timezone')
        return config_tz or 'Asia/Saigon'

    def _get_local_day_bounds(self, employee, work_date):
        timezone_name = self._resolve_timezone_name(employee)
        local_tz = ZoneInfo(timezone_name)
        local_start = datetime.combine(work_date, datetime.min.time(), tzinfo=local_tz)
        local_end = local_start + timedelta(days=1, microseconds=-1)
        return (
            local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None),
        )

    def _to_local_datetime(self, timestamp, timezone_name):
        if not timestamp:
            return False
        local_tz = ZoneInfo(timezone_name)
        if timestamp.tzinfo:
            return timestamp.astimezone(local_tz).replace(tzinfo=None)
        return timestamp.replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)
    
    # ════════════════════════════════════════════════════════════════════════
    # BATCH OPERATIONS
    # ════════════════════════════════════════════════════════════════════════
    
    def generate_daily_sheets_batch(self, work_date=None):
        """
        Generate daily sheets for all employees for a given date
        
        Args:
            work_date (date): Date to generate sheets for (default: today)
        """
        if not work_date:
            work_date = date.today()
        
        try:
            employees = self.env['hr.employee'].sudo().search([
                ('active', '=', True),
            ])
            
            created_sheets = []
            for emp in employees:
                try:
                    sheet = self.generate_daily_sheet(emp.id, work_date)
                    created_sheets.append(sheet)
                except Exception as e:
                    _logger.warning(f'Failed to generate sheet for {emp.name}: {str(e)}')
            
            return {
                'success': True,
                'count': len(created_sheets),
                'sheets': created_sheets,
            }
            
        except Exception as e:
            _logger.exception('Error generating batch daily sheets')
            return {
                'success': False,
                'message': str(e),
            }
    
    # ════════════════════════════════════════════════════════════════════════
    # REPORT GENERATION
    # ════════════════════════════════════════════════════════════════════════
    
    def get_attendance_summary(self, employee_id, month_start, month_end):
        """
        Get monthly attendance summary
        
        Returns:
            dict with summary statistics
        """
        daily_sheets = self.env['daily.sheet'].sudo().search([
            ('employee_id', '=', employee_id),
            ('work_date', '>=', month_start),
            ('work_date', '<=', month_end),
        ])
        
        summary = {
            'total_days': len(daily_sheets),
            'present_days': len(daily_sheets.filtered(lambda x: x.status == 'present')),
            'absent_days': len(daily_sheets.filtered(lambda x: x.status == 'absent')),
            'incomplete_days': len(daily_sheets.filtered(lambda x: x.status == 'incomplete')),
            'late_days': len(daily_sheets.filtered(lambda x: x.is_late)),
            'early_days': len(daily_sheets.filtered(lambda x: x.is_early)),
            'total_hours': sum(daily_sheets.mapped('hours_worked')),
            'total_late_minutes': sum(daily_sheets.mapped('minutes_late')),
            'total_early_minutes': sum(daily_sheets.mapped('minutes_early')),
        }
        
        return summary
