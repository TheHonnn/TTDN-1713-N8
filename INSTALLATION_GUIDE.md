# 🤖 HỆ THỐNG CHẤM CÔNG BẰNG NHẬN DIỆN KHUÔN MẶT AI

## 📋 MỤC LỤC
1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Cài đặt AI Service](#cài-đặt-ai-service)
3. [Cài đặt Module Odoo](#cài-đặt-module-odoo)
4. [Cấu hình](#cấu-hình)
5. [Test API](#test-api)
6. [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
7. [Troubleshooting](#troubleshooting)

---

## 🔧 YÊU CẦU HỆ THỐNG

### Hardware
- Camera/Webcam kết nối USB (để nhận diện khuôn mặt)
- CPU: Intel Core i5 trở lên (hoặc tương đương)
- RAM: 4GB (8GB khuyến nghị)
- Đặc biệt: GPU tùy chọn (giúp xử lý nhanh)

### Software & Libraries
- **Python**: 3.8 - 3.11
- **Odoo**: 16.0+ (đã có hr module)
- **Database**: PostgreSQL

### Python Packages (xem requirements.txt)
```
opencv-python==4.8.1.78      # Video capture & image processing
face_recognition==1.4.0       # Face detection & recognition
face-recognition-models==0.3.0  # Pre-trained models
numpy==1.24.3                 # Matrix operations
requests==2.31.0              # HTTP requests to Odoo API
```

---

## 🚀 CÀI ĐẶT AI SERVICE

### Bước 1: Clone hoặc tạo folder AI Service
```bash
cd ~/TTDN-1713-N8
mkdir -p ai_service
cd ai_service
```

### Bước 2: Tạo Python Virtual Environment
```bash
# Trên Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Trên Windows
python -m venv venv
venv\Scripts\activate
```

### Bước 3: Cài đặt dependencies
```bash
pip install -r requirements.txt
```

**Lưu ý**: Quá trình cài đặt face_recognition có thể mất 5-10 phút (tải models ~100MB)

### Bước 4: Cấu hình file config

Tạo file `ai_service/config.py`:
```python
# Odoo Configuration
ODOO_URL = "http://localhost:8069"
ODOO_API_KEY = "your_secure_api_key_here"
ODOO_DB = "your_odoo_database"

# Dataset Configuration
DATASET_PATH = "./face_dataset"
ENCODINGS_FILE = "./face_dataset/encodings.pickle"
EMPLOYEE_MAPPING_FILE = "./face_dataset/employee_mapping.json"

# Recognition Configuration
CONFIDENCE_THRESHOLD = 0.55
DISTANCE_THRESHOLD = 0.6

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "./face_attendance.log"
```

### Bước 5: Chạy AI Service

```bash
python face_recognition_service.py
```

Bạn sẽ thấy menu:
```
============================================================
🤖 FACE ATTENDANCE RECOGNITION SERVICE
============================================================

📋 MENU:
1. 📸 Chụp ảnh + huấn luyện cho nhân viên
2. 🎥 Chạy webcam nhận diện (chấm công)
3. 📊 Hiển thị số nhân viên trong database
0. ❌ Thoát

Chọn (0-3):
```

---

## 📦 CÀI ĐẶT MODULE ODOO

### Bước 1: Copy module vào addons folder
```bash
# Module đã được tạo tại
~/TTDN-1713-N8/addons/face_attendance/

# Kiểm tra cấu trúc
ls -la ~/TTDN-1713-N8/addons/face_attendance/
# Output:
# __init__.py
# __manifest__.py
# models/
# controllers/
# security/
# views/
```

### Bước 2: Khởi động lại Odoo
```bash
# Tìm process Odoo và kill
pkill -f "odoo-bin"

# Hoặc kiểm tra port
lsof -i :8069

# Khởi động lại với flag update
cd ~/TTDN-1713-N8
./odoo-bin -d your_database --init=face_attendance
```

### Bước 3: Cài đặt module trong Odoo UI

1. Đăng nhập vào Odoo
2. Vào **Apps** → Tìm "Face Attendance"
3. Nhấn **Install**

Hoặc dùng CLI:
```bash
./odoo-bin -d your_database --init=face_attendance -c odoo.conf
```

### Bước 4: Kiểm tra cài đặt

Sau khi cài xong, bạn sẽ thấy:
- ✓ Menu mới: **HR** → **Face Attendance** → **Attendance Logs**
- ✓ Tab mới `Face Recognition` trong từng nhân viên
- ✓ Model mới: `face.attendance.log`

---

## ⚙️ CẤU HÌNH

### 1. Cấu hình API Key


#### Trong Odoo Settings:
```
Settings → Technical → HTTP Headers (nếu có)
```

Hoặc chỉnh trực tiếp trong controller:
```python
# File: addons/face_attendance/controllers/face_attendance_controller.py
# Dòng ~20

VALID_API_KEYS = [
    'your_secure_api_key_here',  # Thay đổi ở đây
    'dev_key_123456',
]
```

**QUAN TRỌNG**: Không để API key vào source code. Nên lưu trong environment variables:
```bash
export ODOO_FACE_ATTENDANCE_API_KEY="your_secure_api_key_here"
```

Rồi trong code:
```python
import os
VALID_API_KEYS = [
    os.environ.get('ODOO_FACE_ATTENDANCE_API_KEY', 'default_key')
]
```

### 2. Cấu hình confidence threshold

Trong model hr.employee, có field `face_confidence_threshold` (default: 0.55)

- **0.3 - 0.4**: Rất nhạy (dễ match nhưng sai nhiều)
- **0.5 - 0.6**: Cân bằng (khuyến nghị)
- **0.7 - 0.9**: Khắt khe (chính xác nhưng dễ từ chối)

### 3. Cấu hình camera

```python
# File: ai_service/face_recognition_service.py
# Dòng ~400

cap = cv2.VideoCapture(0)  # 0 = webcam mặc định
# Hoặc: cv2.VideoCapture(1) # camera thứ 2
# Hoặc: cv2.VideoCapture("rtsp://...") # IP camera
```

---

## 🧪 TEST API

### Phương pháp 1: Sử dụng cURL

```bash
# Health check
curl -X GET "http://localhost:8069/api/face_attendance/health" \
  -H "Content-Type: application/json"

# Response:
# {
#   "status": "healthy",
#   "timestamp": "2024-01-15T10:30:45.123456",
#   "version": "1.0.0"
# }
```

### Phương pháp 2: Test check-in endpoint

Tạo file `test_api.py`:

```python
import requests
import json
from datetime import datetime

ODOO_URL = "http://localhost:8069"
API_KEY = "your_secure_api_key_here"

def test_checkin():
    """Test check-in API"""
    
    endpoint = f"{ODOO_URL}/api/face_attendance/checkin"
    
    payload = {
        "employee_id": 1,  # Thay đổi theo ID nhân viên của bạn
        "timestamp": datetime.now().isoformat(),
        "confidence": 0.95,
        "distance": 0.35,
        "camera_source": "webcam_main"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }
    
    print("📤 Sending request...")
    print(f"URL: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"\n✅ Response Status: {response.status_code}")
        print(f"Response Body:\n{json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_get_employee():
    """Test get employee info"""
    
    endpoint = f"{ODOO_URL}/api/face_attendance/employee/1"
    
    headers = {"X-API-Key": API_KEY}
    
    print("📤 Getting employee info...")
    
    try:
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_get_logs():
    """Test get logs"""
    
    endpoint = f"{ODOO_URL}/api/face_attendance/logs?limit=10"
    
    headers = {"X-API-Key": API_KEY}
    
    print("📤 Getting attendance logs...")
    
    try:
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Test Face Attendance API")
    print("=" * 60)
    
    test_get_employee()
    print("\n" + "-" * 60 + "\n")
    
    test_checkin()
    print("\n" + "-" * 60 + "\n")
    
    test_get_logs()
```

Chạy test:
```bash
python test_api.py
```

### Phương pháp 3: Postman Collection

Tạo file `Face_Attendance_Postman.json`:

```json
{
  "info": {
    "name": "Face Attendance API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "url": {
          "raw": "{{ODOO_URL}}/api/face_attendance/health",
          "host": ["{{ODOO_URL}}"],
          "path": ["api", "face_attendance", "health"]
        },
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ]
      }
    },
    {
      "name": "Check In",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-API-Key",
            "value": "{{API_KEY}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"employee_id\": 1, \"timestamp\": \"2024-01-15T10:30:45\", \"confidence\": 0.95, \"distance\": 0.35, \"camera_source\": \"webcam_main\"}"
        },
        "url": {
          "raw": "{{ODOO_URL}}/api/face_attendance/checkin",
          "host": ["{{ODOO_URL}}"],
          "path": ["api", "face_attendance", "checkin"]
        }
      }
    }
  ],
  "variable": [
    {
      "key": "ODOO_URL",
      "value": "http://localhost:8069"
    },
    {
      "key": "API_KEY",
      "value": "your_secure_api_key_here"
    }
  ]
}
```

Import vào Postman và test.

---

## 📖 HƯỚNG DẪN SỬ DỤNG

### Quy trình hoàn chỉnh

#### 1️⃣ BƯỚC 1: Đăng ký khuôn mặt nhân viên

```bash
# Chạy AI Service
cd ~/TTDN-1713-N8/ai_service
source venv/bin/activate
python face_recognition_service.py

# Chọn: 1 (Chụp ảnh)
# Nhập ID nhân viên
# Nhập số ảnh (mặc định 10)

# Chụp 10 ảnh theo hướng dẫn
# SPACE: chụp
# ESC: dừng
```

**Kết quả**: File encodings.pickle và employee_mapping.json được lưu

#### 2️⃣ BƯỚC 2: Chạy webcam nhận diện

```bash
# Tiếp tục menu
# Chọn: 2 (Chạy webcam)

# Hệ thống sẽ:
# 1. Mở webcam realtime
# 2. Detect khuôn mặt
# 3. So sánh với database
# 4. Tự động gọi API Odoo khi match
# 5. Ghi log vào database
```

#### 3️⃣ BƯỚC 3: Kiểm tra logs trong Odoo

1. Đăng nhập Odoo
2. Vào **HR** → **Face Attendance** → **Attendance Logs**
3. Xem danh sách checks
4. Kiểm tra `is_synced_to_attendance` = True
5. Xem record trong `hr.attendance`

---

## 🐛 TROUBLESHOOTING

### Lỗi: "Không thể mở webcam"

**Nguyên nhân**: Camera không được phát hiện hoặc không có quyền truy cập

**Cách fix**:
```bash
# Kiểm tra camera
ls /dev/video*

# Cấp quyền
sudo usermod -a -G video $USER

# Logout & login lại
```

### Lỗi: "face_recognition không tìm mặt"

**Nguyên nhân**: Ánh sáng kém, khoảng cách quá xa, hoặc mô hình không phù hợp

**Cách fix**:
```python
# Thay 'hog' thành 'cnn' (chính xác hơn nhưng chậm)
face_locations = face_recognition.face_locations(rgb_small_frame, model='cnn')

# Hoặc cải thiện điều kiện ánh sáng, camera setup
```

### Lỗi: "API Key không hợp lệ"

**Nguyên nhân**: API key không matching

**Cách fix**:
1. Kiểm tra lại API key trong config.py
2. Kiểm tra trong controller có đúng key không
3. Thêm log để debug

```python
print(f"Received: {api_key}")
print(f"Valid keys: {self.VALID_API_KEYS}")
```

### Lỗi: "Employee not found"

**Nguyên nhân**: ID nhân viên không tồn tại trong Odoo

**Cách fix**:
1. Kiểm tra employee ID có tồn tại không
2. Xem database Odoo: HR → Employees
3. Sử dụng ID đúng khi test

### Lỗi: "Low confidence match"

**Nguyên nhân**: Độ khớp thấp (< 0.55)

**Cách fix**:
```python
# Hạ threshol ld (nhưng sẽ sai nhiều hơn)
DISTANCE_THRESHOLD = 0.7

# Hoặc chụp lại ảnh với điều kiện tốt hơn
# - Ánh sáng tự nhiên
# - Khoảng cách 30-50cm
# - Hướng thẳng camera
```

### Lỗi: "No attendance record synced"

**Nguyên nhân**: is_synced_to_attendance = False

**Cách fix**:
1. Kiểm tra recognition_status = 'success'
2. Nhấn button "Sync to Attendance" trên form log
3. Kiểm tra hr.attendance model có field check_in không

---

## 📊 FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────┐
│  AI SERVICE (Python)                                │
├─────────────────────────────────────────────────────┤
│  1. Mở Webcam (OpenCV)                              │
│  2. Detect khuôn mặt (face_recognition)             │
│  3. Encode khuôn mặt                                │
│  4. So sánh với database (numpy)                    │
│  5. Lấy employee_id + confidence                    │
└─────────────┬──────────────────────────────────────┘
              │
              │ POST /api/face_attendance/checkin
              │ {employee_id, timestamp, confidence}
              ▼
┌─────────────────────────────────────────────────────┐
│  ODOO API CONTROLLER                                │
├─────────────────────────────────────────────────────┤
│  1. Verify API Key                                  │
│  2. Validate employee exists                        │
│  3. Create face.attendance.log                      │
│  4. Auto-sync to hr.attendance                      │
│  5. Return response                                 │
└─────────────┬──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│  DATABASE TABLES                                    │
├─────────────────────────────────────────────────────┤
│  - face.attendance.log (ghi log chi tiết)          │
│  - hr.attendance (check-in/out chính)              │
│  - hr.employee (extend: face_encoding)             │
└─────────────────────────────────────────────────────┘
```

---

## 👥 EXAMPLE DATA

### Employee Sample
```
ID: 1
Name: John Doe
Department: HR
Face Registered: Yes
Confidence Threshold: 0.55
```

### Attendance Log Sample
```
ID: 100
Employee: John Doe
Check Time: 2024-01-15 10:30:45
Check Type: check_in
Confidence: 0.95
Distance: 0.35
Status: success
Synced: Yes
Attendance ID: 50
```

### HR Attendance Sample
```
ID: 50
Employee: John Doe
Check In: 2024-01-15 10:30:45
Check Out: 2024-01-15 17:45:30
Worked Hours: 7.25
```

---

## 📧 SUPPORT

Nếu gặp vấn đề:

1. Kiểm tra logs: `~/TTDN-1713-N8/ai_service/face_attendance.log`
2. Kiểm tra Odoo logs: Xem `/var/log/odoo/` hoặc terminal window
3. Debug:
   ```python
   # Thêm verbose logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

**Chúc bạn thành công! 🚀**
