# 🤖 Face Attendance Recognition System

Hệ thống chấm công bằng nhận diện khuôn mặt AI cho Odoo ERP

## 📋 Mục Lục

- [Giới Thiệu](#giới-thiệu)
- [Tính Năng](#tính-năng)
- [Yêu Cầu](#yêu-cầu)
- [Cài Đặt Nhanh](#cài-đặt-nhanh)
- [Kiến Trúc Hệ Thống](#kiến-trúc-hệ-thống)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## 🎯 Giới Thiệu

Hệ thống này giúp tự động hóa quy trình chấm công bằng cách:

1. 📸 **Nhận diện khuôn mặt** qua webcam realtime
2. 🔄 **So sánh AI** với database nhân viên
3. 📝 **Chấm công tự động** vào hr.attendance
4. 📊 **Ghi log chi tiết** mỗi lần nhận diện

## ✨ Tính Năng

- ✅ Real-time face detection & recognition
- ✅ Automatic check-in/check-out
- ✅ Odoo integration via REST API
- ✅ Detailed audit logging
- ✅ Confidence scoring
- ✅ Multi-camera support
- ✅ Auto-sync to hr.attendance
- ✅ Duplicate detection

## 🔧 Yêu Cầu

### Hardware
- Webcam hoặc IP camera
- CPU: Intel i5+ hoặc tương đương
- RAM: 4GB minimum (8GB recommended)

### Software
- Python 3.8 - 3.11
- Odoo 16.0+
- PostgreSQL

### Python Packages
- opencv-python
- face_recognition
- numpy
- requests

## 🚀 Cài Đặt Nhanh

### 1. Cài đặt AI Service

```bash
cd ~/TTDN-1713-N8/ai_service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run service
python face_recognition_service.py
```

### 2. Cài đặt Module Odoo

```bash
# Module đã có sẵn tại:
# ~/TTDN-1713-N8/addons/face_attendance/

# Khởi động lại Odoo
pkill -f "odoo-bin"
cd ~/TTDN-1713-N8
./odoo-bin -d your_database --init=face_attendance
```

### 3. Test API

```bash
python test_api.py
```

## 📊 Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────┐
│  AI Service (Python)                            │
├─────────────────────────────────────────────────┤
│  - OpenCV: Capture video từ webcam              │
│  - face_recognition: Detect & encode khuôn mặt │
│  - requests: Call API Odoo                      │
└──────────────────┬──────────────────────────────┘
                   │ POST /api/face_attendance/checkin
                   │ (employee_id, timestamp, confidence)
                   ▼
┌─────────────────────────────────────────────────┐
│  Odoo REST API Controller                       │
├─────────────────────────────────────────────────┤
│  - Validate API key                             │
│  - Find employee                                │
│  - Create face.attendance.log                   │
│  - Auto-sync to hr.attendance                   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  Database                                       │
├─────────────────────────────────────────────────┤
│  - face.attendance.log (chi tiết)               │
│  - hr.attendance (chấm công chính)              │
│  - hr.employee (extend: face_encoding)          │
└─────────────────────────────────────────────────┘
```

## 🔌 API Reference

### 1. Check In

```
POST /api/face_attendance/checkin
Headers: X-API-Key: your_api_key

Request:
{
  "employee_id": 1,
  "timestamp": "2024-01-15T10:30:45.123456",
  "confidence": 0.95,
  "distance": 0.35,
  "camera_source": "webcam_main"
}

Response:
{
  "status": "success",
  "message": "Check-in recorded",
  "data": {
    "log_id": 100,
    "employee_id": 1,
    "check_type": "check_in",
    "confidence": 0.95,
    "attendance_info": {...}
  }
}
```

### 2. Get Employee Info

```
GET /api/face_attendance/employee/<id>
Headers: X-API-Key: your_api_key

Response:
{
  "status": "success",
  "data": {
    "id": 1,
    "name": "John Doe",
    "department": "HR",
    "is_face_registered": true
  }
}
```

### 3. Get Logs

```
GET /api/face_attendance/logs?limit=10&employee_id=1
Headers: X-API-Key: your_api_key

Response:
{
  "status": "success",
  "total": 10,
  "data": [...]
}
```

## 📁 Project Structure

```
~/TTDN-1713-N8/
├── ai_service/
│   ├── face_recognition_service.py       # Main AI service
│   ├── test_api.py                      # API tests
│   ├── config_example.py                # Config template
│   ├── requirements.txt                 # Python deps
│   └── face_dataset/                    # Auto-generated
│       ├── encodings.pickle
│       ├── employee_mapping.json
│       └── employee_1/, employee_2/, ...
│
├── addons/face_attendance/
│   ├── __manifest__.py
│   ├── controllers/
│   │   └── face_attendance_controller.py
│   ├── models/
│   │   ├── hr_employee_extend.py
│   │   └── face_attendance_log.py
│   ├── security/
│   │   └── ir.model.access.csv
│   ├── views/
│   │   ├── hr_employee_extend_views.xml
│   │   ├── face_attendance_log_views.xml
│   │   └── menu.xml
│   └── __init__.py
│
├── INSTALLATION_GUIDE.md    # Full installation guide
├── QUICK_START.py          # Quick start examples
└── README.md               # This file
```

## 🎓 Workflow

### 1️⃣ Register Employee Face

```bash
python face_recognition_service.py
# Menu 1: Capture face images
# 10 samples per employee
```

### 2️⃣ Run Webcam Recognition

```bash
python face_recognition_service.py
# Menu 2: Start real-time recognition
# Automatically calls Odoo API
```

### 3️⃣ View Logs in Odoo

```
HR → Face Attendance → Attendance Logs
```

## 🔐 Security

- ✅ API key authentication
- ✅ Request validation
- ✅ Audit logging
- ✅ Duplicate detection
- ✅ Field-level access control

### Important

- Never commit API keys to git
- Use environment variables in production
- Enable HTTPS for API calls
- Rotate API keys regularly

## 📊 Monitoring

### View Logs

```bash
tail -f ~/TTDN-1713-N8/ai_service/face_attendance.log
```

### Check Status

- AI Service running: `ps aux | grep face_recognition_service`
- Odoo running: `ps aux | grep odoo-bin`
- API health: GET `/api/face_attendance/health`

## 🐛 Troubleshooting

### "Cannot open webcam"
```bash
# Check device
ls /dev/video*

# Grant permission
sudo usermod -a -G video $USER
```

### "No face detected"
- Improve lighting
- Get closer to camera
- Look directly at camera

### "Low confidence match"
- Re-register with more samples
- Adjust DISTANCE_THRESHOLD
- Improve camera setup

### "API connection failed"
- Check Odoo is running
- Verify ODOO_URL
- Check API key

## 📚 Documentation

- [Installation Guide](INSTALLATION_GUIDE.md) - Detailed setup steps
- [Quick Start](QUICK_START.py) - Quick reference
- [Code Comments](addons/face_attendance/models/) - Detailed code docs

## 🎯 Next Steps

1. ✅ Clone/setup repository
2. ✅ Install AI Service
3. ✅ Install Odoo Module
4. ✅ Register employee faces
5. ✅ Run webcam recognition
6. ✅ Monitor attendance logs

## 📞 Support

For issues or questions:
1. Check troubleshooting guide
2. Review logs
3. Test API endpoints
4. Consult documentation

## 📄 License

This project is part of TTDN-1713-N8

## 👨‍💻 Author

Senior Odoo Developer + AI Engineer

---

**Status**: ✅ Ready for Production

**Last Updated**: 2024-01-15

**Version**: 1.0.0
