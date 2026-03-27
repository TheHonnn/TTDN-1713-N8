# -*- coding: utf-8 -*-
import base64
import json
import logging
from io import BytesIO

import numpy as np
from PIL import Image

try:
    import face_recognition
except ImportError:
    face_recognition = None

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class NhanVien(models.Model):
    _inherit = 'nhan_vien'

    face_encoding = fields.Text(
        string='Dữ liệu khuôn mặt (Vector)',
        help='Chuỗi mã hóa khuôn mặt dùng để AI so khớp',
        copy=False,
    )

    is_face_registered = fields.Boolean(
        string='Đã đăng ký FaceID',
        compute='_compute_face_registered',
        store=True,
    )

    @api.depends('face_encoding')
    def _compute_face_registered(self):
        for record in self:
            record.is_face_registered = bool(record.face_encoding)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._auto_sync_face_encoding_on_image_change(vals_list)
        return records

    def write(self, vals):
        result = super().write(vals)
        self._auto_sync_face_encoding_after_write(vals)
        return result

    def action_generate_face_encoding(self):
        self.ensure_one()
        self._store_face_encoding_from_photo(raise_if_missing=True)
        return {
            'effect': {
                'fadeout': 'slow',
                'message': _('Đã đăng ký FaceID thành công cho %s!') % self.ho_va_ten,
                'type': 'rainbow_man',
            }
        }

    @api.model
    def action_generate_missing_face_encodings(self):
        employees = self.search([('anh', '!=', False)])
        processed = 0
        generated = 0
        failed = []

        for employee in employees:
            processed += 1
            try:
                created = employee._store_face_encoding_from_photo(raise_if_missing=False)
                if created:
                    generated += 1
            except Exception as exc:
                failed.append(f'{employee.ma_dinh_danh or employee.id}: {exc}')

        return {
            'processed': processed,
            'generated': generated,
            'failed': failed,
        }

    @api.model
    def identify_employee(self, captured_image_base64):
        employee, _confidence, _distance = self._match_employee_from_image(captured_image_base64)
        return employee or False

    def identify_face_ai(self, captured_base64):
        if not captured_base64:
            return {'status': 'fail', 'message': _('Ảnh trống!')}

        try:
            employee, confidence, distance = self._match_employee_from_image(captured_base64)
            if not employee:
                return {'status': 'fail', 'message': _('Không nhận diện được!')}

            attendance_result = employee._record_face_match_attendance(confidence, distance)
            if attendance_result.get('status') not in ('success', 'warning'):
                return attendance_result

            return {
                'status': 'success',
                'name': employee.ho_va_ten,
                'employee_id': employee.ma_dinh_danh,
                'confidence': confidence,
                'message': attendance_result.get('message') or _('Đã ghi nhận chấm công'),
                'check_time': attendance_result.get('timestamp') or fields.Datetime.now().strftime('%H:%M:%S'),
                'check_type': attendance_result.get('check_type'),
            }
        except Exception as exc:
            _logger.exception('Face identify failed')
            return {'status': 'error', 'message': str(exc)}

    def _auto_sync_face_encoding_on_image_change(self, vals_list):
        for record, vals in zip(self, vals_list):
            if 'anh' not in vals:
                continue
            record._handle_face_encoding_after_image_update()

    def _auto_sync_face_encoding_after_write(self, vals):
        if 'anh' not in vals:
            return
        for record in self:
            record._handle_face_encoding_after_image_update()

    def _handle_face_encoding_after_image_update(self):
        self.ensure_one()
        if not self.anh:
            self.face_encoding = False
            return
        self._store_face_encoding_from_photo(raise_if_missing=False)

    def _ensure_face_recognition_ready(self):
        if face_recognition is None:
            raise UserError(_('Thiếu thư viện face_recognition trong môi trường Odoo.'))

    def _normalize_base64_image(self, image_base64):
        if not image_base64:
            raise UserError(_('Ảnh không hợp lệ.'))
        if isinstance(image_base64, bytes):
            image_base64 = image_base64.decode()
        if ',' in image_base64:
            image_base64 = image_base64.split(',', 1)[1]
        return image_base64.strip()

    def _decode_image_array(self, image_base64):
        encoded = self._normalize_base64_image(image_base64)
        image_bytes = base64.b64decode(encoded)
        image = Image.open(BytesIO(image_bytes)).convert('RGB')
        return np.array(image)

    def _extract_face_encoding(self, image_base64, raise_if_missing=True):
        self._ensure_face_recognition_ready()
        try:
            image_array = self._decode_image_array(image_base64)
            encodings = face_recognition.face_encodings(image_array)
        except Exception as exc:
            if raise_if_missing:
                raise UserError(_('Không đọc được ảnh khuôn mặt: %s') % exc)
            _logger.warning('Failed to read face image for employee %s: %s', self.ids, exc)
            return False

        if not encodings:
            if raise_if_missing:
                raise UserError(_('Không tìm thấy khuôn mặt hợp lệ trong ảnh.'))
            return False

        return encodings[0]

    def _store_face_encoding_from_photo(self, raise_if_missing=False):
        self.ensure_one()
        if not self.anh:
            if raise_if_missing:
                raise UserError(_('Chưa có ảnh nhân viên để đăng ký FaceID.'))
            self.face_encoding = False
            return False

        encoding = self._extract_face_encoding(self.anh, raise_if_missing=raise_if_missing)
        if encoding is False:
            return False

        self.face_encoding = json.dumps(encoding.tolist())
        return True

    def _get_registered_face_candidates(self):
        employees = self.search([('face_encoding', '!=', False)])
        candidates = []
        for employee in employees:
            try:
                candidates.append((employee, np.array(json.loads(employee.face_encoding))))
            except Exception:
                _logger.warning('Invalid face encoding stored for employee %s', employee.id)
        return candidates

    @api.model
    def _match_employee_from_image(self, captured_image_base64, tolerance=0.6):
        captured_encoding = self._extract_face_encoding(captured_image_base64, raise_if_missing=False)
        if captured_encoding is False:
            return self.browse(), 0.0, 1.0

        candidates = self._get_registered_face_candidates()
        if not candidates:
            return self.browse(), 0.0, 1.0

        best_employee = self.browse()
        best_distance = None
        for employee, known_encoding in candidates:
            distance = float(face_recognition.face_distance([known_encoding], captured_encoding)[0])
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_employee = employee

        if best_distance is None or best_distance > tolerance:
            return self.browse(), 0.0, best_distance if best_distance is not None else 1.0

        confidence = max(0.0, min(1.0, 1 - (best_distance / tolerance)))
        return best_employee, confidence, best_distance

    def _record_face_match_attendance(self, confidence, distance):
        self.ensure_one()
        payload = {
            'employee_id': self.id,
            'employee_code': self.ma_dinh_danh,
            'timestamp': fields.Datetime.now(),
            'confidence': confidence,
            'distance': distance or 0.0,
            'camera_source': 'odoo_webcam',
        }

        try:
            return self.env['attendance.ai.service'].sudo().process_checkin(payload)
        except KeyError:
            _logger.warning('attendance.ai.service is unavailable, falling back to direct hr.attendance create')
        except Exception as exc:
            _logger.exception('Attendance AI service failed, falling back to direct hr.attendance create')
            return {
                'status': 'error',
                'message': str(exc),
            }

        employee = self._get_or_create_hr_employee()
        attendance = self.env['hr.attendance'].sudo().create({
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
            'is_face_recognition': True,
            'face_confidence': confidence,
        })
        return {
            'status': 'success',
            'message': _('Đã tạo chấm công trực tiếp.'),
            'timestamp': attendance.check_in,
            'check_type': 'check_in',
        }

    def _get_or_create_hr_employee(self):
        self.ensure_one()
        employee_model = self.env['hr.employee'].sudo()
        employee = employee_model.search([('nhan_vien_id', '=', self.id)], limit=1)
        if not employee and self.ma_dinh_danh:
            employee = employee_model.search([
                '|',
                ('barcode', '=', self.ma_dinh_danh),
                ('identification_id', '=', self.ma_dinh_danh),
            ], limit=1)

        values = {
            'name': self.ho_va_ten,
            'barcode': self.ma_dinh_danh,
            'identification_id': self.ma_dinh_danh,
            'work_email': self.email,
            'mobile_phone': self.so_dien_thoai,
            'company_id': self.company_id.id or self.env.company.id,
            'nhan_vien_id': self.id,
        }
        if employee:
            employee.write(values)
            return employee
        return employee_model.create(values)