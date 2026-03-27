# -*- coding: utf-8 -*-
"""
Controller: Face Attendance API
REST API endpoints cho AI Service
"""

from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class FaceAttendanceAPI(http.Controller):

    def _json_response(self, payload, status=200):
        response = request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
        )
        response.status_code = status
        return response
    
    # ════════════════════════════════════════════════════════════════════════
    # ROUTES
    # ════════════════════════════════════════════════════════════════════════
    
    @http.route(
        '/api/face_attendance/checkin',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def checkin(self):
        """
        POST /api/face_attendance/checkin
        
        Điểm danh dựa trên nhận diện khuôn mặt
        
        Request:
        {
            "employee_code": "005",
            "timestamp": "2026-03-26T08:05:00",
            "confidence": 0.95
        }
        
        Response (Success):
        {
            "status": "success",
            "employee_id": 5,
            "employee_name": "Nguyễn Văn Vinh",
            "check_type": "check_in",
            "is_late": true,
            "message": "Check-in recorded successfully"
        }
        
        Response (Error):
        {
            "status": "error",
            "code": "EMPLOYEE_NOT_FOUND",
            "message": "Employee E001 not found"
        }
        """
        try:
            # Get request data
            data = self._get_json_payload()
            payload = self._normalize_payload(data)
            
            # Get client info
            ip_address = request.httprequest.remote_addr
            
            # Verify API key (if configured)
            # api_key = request.httprequest.headers.get('X-API-Key')
            # security_service = request.env['security.service']
            # if api_key:
            #     auth_result = security_service.verify_api_key(api_key)
            #     if not auth_result['valid']:
            #         return {
            #             'status': 'error',
            #             'code': 'UNAUTHORIZED',
            #             'message': auth_result['message'],
            #         }
            
            # Process checkin
            ai_service = request.env['attendance.ai.service']
            result = ai_service.process_checkin(payload)
            
            return result
            
        except json.JSONDecodeError:
            return {
                'status': 'error',
                'code': 'INVALID_JSON',
                'message': 'Invalid JSON payload',
            }
        except Exception as e:
            _logger.error(f"API error: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'code': 'INTERNAL_ERROR',
                'message': 'Internal server error',
            }
    
    @http.route(
        '/api/face_attendance/health',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def health_check(self):
        """
        GET /api/face_attendance/health
        
        Health check endpoint
        """
        return self._json_response({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'nhan_su_ai_service',
            'version': '1.0.0',
        })
    
    @http.route(
        '/api/face_attendance/employee/<int:employee_id>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def get_employee(self, employee_id):
        """
        GET /api/face_attendance/employee/<id>
        
        Lấy thông tin nhân viên
        """
        try:
            employee = request.env['nhan_vien'].sudo().browse(employee_id)
            
            if not employee.exists():
                return self._json_response({
                    'status': 'error',
                    'code': 'EMPLOYEE_NOT_FOUND',
                    'message': f'Employee {employee_id} not found',
                }, status=404)
            
            return self._json_response({
                'status': 'success',
                'data': {
                    'id': employee.id,
                    'code': employee.ma_dinh_danh,
                    'name': employee.ho_va_ten,
                    'department': employee.phong_ban_id.ten_phong_ban if employee.phong_ban_id else None,
                    'job_title': employee.chuc_vu_id.ten_chuc_vu if employee.chuc_vu_id else None,
                }
            })
        except Exception as e:
            _logger.error(f"Error fetching employee: {str(e)}")
            return self._json_response({
                'status': 'error',
                'code': 'INTERNAL_ERROR',
                'message': str(e),
            }, status=500)
    
    @http.route(
        '/api/face_attendance/logs',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def get_logs(self):
        """
        GET /api/face_attendance/logs?limit=10&employee_id=5
        
        Lấy danh sách logs
        """
        try:
            limit = int(request.httprequest.args.get('limit', 10))
            employee_id = request.httprequest.args.get('employee_id')
            
            domain = []
            if employee_id:
                domain.append(('nhan_vien_id', '=', int(employee_id)))
            
            logs = request.env['ai.request.log'].sudo().search(
                domain,
                order='created_at desc',
                limit=limit
            )
            
            return self._json_response({
                'status': 'success',
                'total': len(logs),
                'data': [
                    {
                        'id': log.id,
                        'request_id': log.request_id,
                        'employee_code': log.employee_code,
                        'employee_name': log.nhan_vien_id.ho_va_ten if log.nhan_vien_id else (log.employee_id.name if log.employee_id else None),
                        'status': log.status,
                        'created_at': log.created_at.isoformat(),
                        'processing_time_ms': log.processing_time,
                    }
                    for log in logs
                ]
            })
        except Exception as e:
            _logger.error(f"Error fetching logs: {str(e)}")
            return self._json_response({
                'status': 'error',
                'code': 'INTERNAL_ERROR',
                'message': str(e),
            }, status=500)
    
    # ════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════════════

    def _get_json_payload(self):
        """Return the payload for Odoo json routes, supporting both raw JSON and JSON-RPC."""
        data = request.jsonrequest or {}
        if isinstance(data, dict) and 'params' in data and set(data.keys()) <= {'jsonrpc', 'method', 'params', 'id'}:
            return data.get('params') or {}
        return data
    
    def _normalize_payload(self, data):
        """Normalize incoming payload"""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        return data
