# -*- coding: utf-8 -*-
"""
Model: AI Request Log
Ghi lại tất cả các request từ AI Service để audit trail
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError
import json
from datetime import date, datetime


class AIRequestLog(models.Model):
    _name = 'ai.request.log'
    _description = 'AI Service Request Log'
    _order = 'created_at desc'
    
    # ════════════════════════════════════════════════════════════════════════
    # FIELDS
    # ════════════════════════════════════════════════════════════════════════
    
    # Request Info
    request_id = fields.Char(
        'Request ID',
        required=True,
        index=True,
        readonly=True
    )
    
    endpoint = fields.Char(
        'Endpoint',
        required=True,
        readonly=True,
        help='API endpoint called'
    )
    
    ip_address = fields.Char(
        'IP Address',
        readonly=True,
        help='Source IP of the request'
    )
    
    # Request Data
    request_payload = fields.Text(
        'Request Payload',
        readonly=True,
        help='JSON payload của request'
    )
    
    response_payload = fields.Text(
        'Response Payload',
        readonly=True,
        help='JSON response trả về'
    )
    
    # Employee Info
    employee_code = fields.Char(
        'Employee Code',
        readonly=True,
        index=True
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        'Employee',
        readonly=True
    )

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        'Nhân viên QLNS',
        readonly=True,
        ondelete='set null'
    )
    
    # Status
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('validation_error', 'Validation Error'),
            ('duplicate', 'Duplicate'),
        ],
        default='pending',
        readonly=True,
        index=True
    )
    
    error_message = fields.Text(
        'Error Message',
        readonly=True
    )
    
    # Processing Time
    request_timestamp = fields.Datetime(
        'Request Timestamp',
        readonly=True,
        help='Timestamp từ request'
    )
    
    processing_time = fields.Float(
        'Processing Time (ms)',
        readonly=True,
        help='Thời gian xử lý request'
    )
    
    created_at = fields.Datetime(
        'Created At',
        default=lambda self: datetime.now(),
        readonly=True
    )
    
    # Reference
    attendance_event_id = fields.Many2one(
        'ai.attendance.event',
        'Attendance Event',
        readonly=True,
        ondelete='set null'
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # METHODS
    # ════════════════════════════════════════════════════════════════════════
    
    def get_request_json(self):
        """Get request payload as dict"""
        try:
            return json.loads(self.request_payload) if self.request_payload else {}
        except:
            return {}
    
    def get_response_json(self):
        """Get response payload as dict"""
        try:
            return json.loads(self.response_payload) if self.response_payload else {}
        except:
            return {}
    
    @api.model
    def _json_dumps_safe(self, value):
        """Serialize values for audit logging without failing on datetimes or records."""
        def _default_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if hasattr(obj, 'ids'):
                return obj.ids
            return str(obj)

        return json.dumps(value or {}, default=_default_serializer)

    @api.model
    def create_log(self, data):
        """
        Tạo log record từ request data
        
        Args:
            data (dict): {
                'request_id': str,
                'endpoint': str,
                'ip_address': str,
                'request_payload': dict,
                'employee_code': str,
                'request_timestamp': datetime,
                'status': str,
                'error_message': str (optional),
                'response_payload': dict (optional),
                'processing_time': float (optional),
                'attendance_event_id': int (optional),
            }
        
        Returns:
            ai.request.log record
        """
        log_data = {
            'request_id': data.get('request_id'),
            'endpoint': data.get('endpoint'),
            'ip_address': data.get('ip_address'),
            'request_payload': self._json_dumps_safe(data.get('request_payload', {})),
            'response_payload': self._json_dumps_safe(data.get('response_payload', {})),
            'employee_code': data.get('employee_code'),
            'request_timestamp': data.get('request_timestamp'),
            'status': data.get('status', 'pending'),
            'error_message': data.get('error_message'),
            'processing_time': data.get('processing_time'),
            'attendance_event_id': data.get('attendance_event_id'),
        }

        nhan_vien_id = data.get('nhan_vien_id')
        if nhan_vien_id:
            nhan_vien = self.env['nhan_vien'].browse(nhan_vien_id)
            if nhan_vien.exists():
                log_data['nhan_vien_id'] = nhan_vien.id
        
        # Try to find employee using explicit id first, then fallback identifiers.
        employee_id = data.get('employee_id')
        if employee_id:
            emp = self.env['hr.employee'].browse(employee_id)
            if emp.exists():
                log_data['employee_id'] = emp.id
        elif data.get('employee_code'):
            emp = self.env['hr.employee'].search(
                ['|', ('barcode', '=', data.get('employee_code')), ('identification_id', '=', data.get('employee_code'))],
                limit=1
            )
            if emp:
                log_data['employee_id'] = emp.id

        if not log_data.get('nhan_vien_id') and log_data.get('employee_id'):
            emp = self.env['hr.employee'].browse(log_data['employee_id'])
            if emp.exists() and emp.nhan_vien_id:
                log_data['nhan_vien_id'] = emp.nhan_vien_id.id

        if not log_data.get('nhan_vien_id') and data.get('employee_code'):
            nhan_vien = self.env['nhan_vien'].search([
                ('ma_dinh_danh', '=', data.get('employee_code')),
            ], limit=1)
            if nhan_vien:
                log_data['nhan_vien_id'] = nhan_vien.id
        
        return self.create(log_data)
