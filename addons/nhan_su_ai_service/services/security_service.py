# -*- coding: utf-8 -*-
"""
Service: SecurityService
Xử lý authentication & authorization cho API
"""

from odoo import models, fields
from odoo.exceptions import AccessError
import hmac
import hashlib
import logging
import uuid

_logger = logging.getLogger(__name__)


class SecurityService(models.AbstractModel):
    _name = 'security.service'
    _description = 'Security Service'
    
    # ════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ════════════════════════════════════════════════════════════════════════
    
    def verify_api_key(self, api_key):
        """
        Verify API key from request
        
        Args:
            api_key (str): API key from header
        
        Returns:
            dict: {
                'valid': bool,
                'user_id': int (if valid),
                'message': str,
            }
        """
        if not api_key:
            return {
                'valid': False,
                'message': 'Missing API key',
            }
        
        # Get config API key (should be in ir.config_parameter)
        config_key = self.env['ir.config_parameter'].sudo().get_param(
            'nhan_su_ai_service.api_key',
            default=None
        )
        
        if not config_key:
            return {
                'valid': False,
                'message': 'API key not configured',
            }
        
        # Compare keys (timing-safe comparison)
        is_valid = hmac.compare_digest(api_key, config_key)
        
        if not is_valid:
            _logger.warning(f"Invalid API key attempt: {api_key[:10]}*")
            return {
                'valid': False,
                'message': 'Invalid API key',
            }
        
        # Find or create system user for API
        user = self.env['res.users'].sudo().search(
            [('login', '=', 'ai_service_bot')],
            limit=1
        )
        
        if not user:
            # Create API user nếu chưa có
            user = self._create_api_user()
        
        return {
            'valid': True,
            'user_id': user.id,
            'message': 'API key verified',
        }
    
    def _create_api_user(self):
        """Tạo system user cho API"""
        company = self.env['res.company'].sudo().search([], limit=1)
        
        return self.env['res.users'].sudo().create({
            'name': 'AI Service Bot',
            'login': 'ai_service_bot',
            'password': 'ai_service_bot_' + str(uuid.uuid4()),
            'email': 'bot@aiservice.internal',
            'company_id': company.id,
            'groups_id': [(4, self.env.ref('base.group_system').id)],
            'active': True,
        })
    
    # ════════════════════════════════════════════════════════════════════════
    # RATE LIMITING
    # ════════════════════════════════════════════════════════════════════════
    
    def check_rate_limit(self, ip_address, max_requests=100, window_seconds=60):
        """
        Simple rate limiting by IP
        
        Args:
            ip_address (str): Client IP
            max_requests (int): Max requests per window
            window_seconds (int): Time window in seconds
        
        Returns:
            dict: {
                'allowed': bool,
                'remaining': int,
                'reset_time': datetime,
            }
        """
        from datetime import datetime, timedelta
        
        # In production, use Redis for better performance
        # For now, use database
        
        key = f"ai_api:rate_limit:{ip_address}"
        cache = self.env['ir.attachment'].sudo().search([
            ('res_field', '=', 'rate_limit'),
            ('name', '=', key),
        ], limit=1)
        
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=window_seconds)
        
        if cache:
            # Check if within window
            if cache.create_date > cutoff_time:
                count = int(cache.datas_fname or '0') + 1
            else:
                count = 1
                cache.write({'datas_fname': '0'})
        else:
            count = 1
        
        allowed = count <= max_requests
        remaining = max(0, max_requests - count)
        reset_time = now + timedelta(seconds=window_seconds)
        
        return {
            'allowed': allowed,
            'remaining': remaining,
            'reset_time': reset_time,
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # AUDIT LOGGING
    # ════════════════════════════════════════════════════════════════════════
    
    def log_security_event(self, event_type, description, ip_address=None, user_id=None):
        """
        Log security-related events
        
        Args:
            event_type (str): 'api_call', 'auth_failed', 'duplicate', etc.
            description (str): Event description
            ip_address (str): Client IP
            user_id (int): User ID (if authenticated)
        """
        self.env['ai.request.log'].sudo().create({
            'endpoint': event_type,
            'ip_address': ip_address,
            'status': 'security_event',
            'error_message': description,
        })
