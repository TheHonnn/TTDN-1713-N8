from odoo import http
from odoo.http import request
import datetime

class FaceEventController(http.Controller):

    # Tạo đường dẫn API: /api/attendance/face_scan
    @http.route('/api/attendance/face_scan', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_face_scan_data(self, **kw):
        """
        Camera ở ngoài sẽ gửi lên 1 cục JSON dạng:
        {
            "ma_dinh_danh": "NV001",
            "camera_source": "Camera Cửa Chính",
            "confidence": 98.5
        }
        """
        # Lấy dữ liệu từ Request do Camera gửi tới
        ma_dinh_danh = kw.get('ma_dinh_danh')
        camera_source = kw.get('camera_source', 'Không xác định')
        confidence = kw.get('confidence', 0.0)

        # 1. Kiểm tra xem có gửi mã định danh lên không
        if not ma_dinh_danh:
            return {'status': 'error', 'message': 'Thiếu mã định danh (ma_dinh_danh)'}

        # 2. Tìm nhân viên trong model 'nhan_vien' dựa vào mã định danh
        # Dùng sudo() để vượt qua phân quyền vì API đang gọi ở chế độ auth='public'
        nhan_vien = request.env['nhan_vien'].sudo().search([('ma_dinh_danh', '=', ma_dinh_danh)], limit=1)

        if not nhan_vien:
            return {'status': 'error', 'message': f'Không tìm thấy nhân viên có mã: {ma_dinh_danh}'}

        # 3. Ghi dữ liệu vào bảng lịch sử quét (attendance.event)
        try:
            event_val = {
                'nhan_vien_id': nhan_vien.id,
                'check_time': datetime.datetime.now(),
                'camera_source': camera_source,
                'confidence_score': confidence,
            }
            request.env['attendance.event'].sudo().create(event_val)
            
            return {
                'status': 'success', 
                'message': f'Đã ghi nhận thành công cho: {nhan_vien.ho_va_ten}'
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Lỗi hệ thống Odoo: {str(e)}'}