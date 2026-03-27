# 🤖 AI Face Service (Python Standalone)

**Status: SETUP COMPLETE ✅**

Nhận diện khuôn mặt từ webcam → Gửi request tới Odoo API

## 📂 Cấu Trúc

```
/home/buih7/TTDN-1713-N8/ai_face_service/
├── face_recognition_service.py    ← Main app
├── requirements.txt               ← Python dependencies
├── __init__.py
└── face_dataset/                  ← Encodings được lưu ở đây (tạo tự động)
    ├── encodings.pickle           ← Face encodings của nhân viên
    └── employee_mapping.json      ← Mapping employee_id
```

## 🚀 Quick Start

### 1. Tạo venv và cài dependencies

```bash
cd /home/buih7/TTDN-1713-N8/ai_face_service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Chạy service

```bash
python face_recognition_service.py
```

Menu sẽ hiện ra:
```
📋 MENU:
1. 📸 Chụp ảnh + huấn luyện cho nhân viên
2. 🎥 Chạy webcam nhận diện (chấm công)
3. 📊 Hiển thị số nhân viên trong database
0. ❌ Thoát
```

### 3. Workflow

**Step 1**: Chọn `1` - Chụp ảnh các nhân viên
- Nhập ID nhân viên (phải match với hr.employee.code trong Odoo)
- Chụp 10-20 ảnh (nhấn SPACE để chụp, ESC để xong)
- Face encodings tự động lưu vào `face_dataset/`

**Step 2**: Chọn `2` - Nhận diện real-time
- Webcam bắt đầu chạy
- Khi nhận diện được khuôn mặt → Gửi HTTP POST tới `/api/face_attendance/checkin`
- Odoo API nhận request → Xử lý chấm công → Record vào hr.attendance

## ⚙️ Configuration

**File**: `face_recognition_service.py` (lines 26-33)

```python
ODOO_URL = "http://localhost:8069"              # ← Đổi nếu Odoo ở server khác
ODOO_API_KEY = "your_secure_api_key_here"      # ← API key từ Odoo
CONFIDENCE_THRESHOLD = 0.55                      # ← Độ tin cậy tối thiểu (0-1)
DISTANCE_THRESHOLD = 0.6                         # ← Khoảng cách tối đa cho match
```

## 🔗 API Communication

Service gọi Odoo tại:
```
POST /api/face_attendance/checkin
Content-Type: application/json
X-API-Key: your_secure_api_key_here

{
  "employee_code": "E001",
  "timestamp": "2026-03-26T10:35:45",
  "confidence": 0.98,
  "camera_source": "webcam_main",
  "distance": 0.35
}
```

Response từ Odoo:
```json
{
  "status": "success",
  "employee_id": 5,
  "employee_name": "Nguyễn Văn A",
  "check_type": "check_in",
  "is_late": true,
  "message": "Check-in recorded successfully"
}
```

## 📊 Dependencies

- `opencv-python`: Webcam capture & frame processing
- `face_recognition`: Face detection & encoding
- `numpy`: Numerical computations
- `requests`: HTTP API calls
- `dlib`: Core ML library (face detection backend)

## 🐛 Troubleshooting

**Lỗi: "Không thể mở webcam"**
- Kiểm tra webcam có kết nối không: `sudo lsusb | grep Camera`
- Kiểm tra permissions: `ls -l /dev/video*`
- Hoặc thử: `sudo usermod -aG video $USER`

**Lỗi: "Kết nối Odoo thất bại"**
- Kiểm tra Odoo đang chạy: `ps aux | grep odoo-bin`
- Verify Odoo URL & port đúng không
- Check API key valid

**Webcam chậm / không responsive**
- Tăng resolution trong camera settings
- Giảm CONFIDENCE_THRESHOLD
- Thử model `'cnn'` thay `'hog'` (chính xác hơn nhưng chậm hơn)

## 📝 Logs

Tất cả hoạt động được ghi vào:
- **Console**: Real-time output
- **File**: `face_attendance.log` (ở folder chạy service)

---

**Phần còn lại của hệ thống:**
- `addons/nhan_su_ai_service/` ← Odoo REST API Gateway (Module 1)
- `addons/nhan_su_attendance_ai/` ← Event Processing (Module 2)
- `addons/nhan_su_attendance_policy/` ← Rules Engine (Module 3)
