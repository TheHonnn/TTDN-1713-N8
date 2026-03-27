from odoo import models, fields, api

class AttendanceEvent(models.Model):
    _name = 'attendance.event'
    _description = 'Lịch sử quét khuôn mặt AI (Thô)'
    _order = 'check_time desc'

    # Đổi tên trường thành nhan_vien_id và trỏ tới model 'nhan_vien'
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, index=True)
    
    check_time = fields.Datetime(string='Thời gian quét', default=fields.Datetime.now, required=True)
    camera_source = fields.Char(string='Camera / Cửa', default='Cửa chính')
    confidence_score = fields.Float(string='Độ chính xác AI (%)')
    image_snapshot = fields.Binary(string='Ảnh chụp', attachment=True)    
    @api.model
    def create(self, vals):
        # 1. Tạo bản ghi lịch sử 
        res = super(AttendanceEvent, self).create(vals)
        
        # 2. TỰ ĐỘNG CẬP NHẬT SANG BẢNG CÔNG (Daily Sheet)
        # Tìm bảng công của nhân viên này trong ngày hôm nay
        today = res.check_time.date()
        daily_sheet = self.env['daily.sheet'].search([
            ('nhan_vien_id', '=', res.nhan_vien_id.id),
            ('ngay', '=', today)
        ], limit=1)

        if daily_sheet:
            # Nếu tìm thấy bảng công, gọi hàm cập nhật giờ từ camera
            daily_sheet.action_lay_du_lieu_camera()
            
        return res                                                                          