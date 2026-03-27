"""
QUICK START GUIDE - Face Attendance System
Hướng dẫn cài đặt nhanh cho nhà phát triển
"""

# ============================================================================
# STEP 1: AI SERVICE SETUP
# ============================================================================

"""
1. Mở terminal và cd vào ai_service
   $ cd ~/TTDN-1713-N8/ai_service

2. Tạo virtual environment
   $ python3 -m venv venv
   $ source venv/bin/activate

3. Cài dependencies
   $ pip install -r requirements.txt

4. Chạy AI Service
   $ python face_recognition_service.py
   
   Menu sẽ hiện:
   1. Chụp ảnh + huấn luyện
   2. Chạy webcam nhận diện
   3. Hiển thị database
   0. Thoát
"""

# ============================================================================
# STEP 2: ODOO MODULE SETUP
# ============================================================================

"""
1. Đảm bảo module đã ở trong ~/TTDN-1713-N8/addons/face_attendance/

2. Khởi động lại Odoo
   $ pkill -f "odoo-bin"
   $ cd ~/TTDN-1713-N8
   $ ./odoo-bin -d your_database --init=face_attendance

3. Kiểm tra trong Odoo UI
   - HR → Face Attendance → Attendance Logs
   - HR → Employees → (mở nhân viên) → Face Recognition tab
"""

# ============================================================================
# STEP 3: FIRST TIME SETUP
# ============================================================================

"""
📋 Workflow:

1. REGISTER EMPLOYEE FACE:
   a. Run AI Service → Menu 1 (Chụp ảnh)
   b. Input employee ID (ví dụ: 1)
   c. Press SPACE 10 lần để chụp ảnh
   d. Press ESC để kết thúc
   
   Result:
   ✓ face_dataset/employee_1/ tạo
   ✓ encodings.pickle cập nhật
   ✓ employee_mapping.json cập nhật

2. RUN WEBCAM RECOGNITION:
   a. Run AI Service → Menu 2 (Chạy webcam)
   b. Định hướng mặt vào camera
   c. Hệ thống sẽ tự động nhận diện
   d. API sẽ gọi Odoo để chấm công
   
   Result:
   ✓ face.attendance.log tạo
   ✓ hr.attendance tạo/cập nhật
   ✓ Logs hiển thị trong Odoo

3. CHECK LOGS IN ODOO:
   a. Đăng nhập Odoo
   b. HR → Face Attendance → Attendance Logs
   c. Xem chi tiết record
   d. Kiểm tra is_synced_to_attendance = True
"""

# ============================================================================
# KEY FILES & LOCATIONS
# ============================================================================

"""
📁 PROJECT STRUCTURE:

~/TTDN-1713-N8/
├── ai_service/
│   ├── face_recognition_service.py    # Main AI service
│   ├── requirements.txt                # Python dependencies
│   ├── test_api.py                    # Test script
│   ├── config.py                      # Configuration (create yourself)
│   ├── face_dataset/
│   │   ├── encodings.pickle           # Face encodings (auto-created)
│   │   ├── employee_mapping.json      # Employee mapping (auto-created)
│   │   └── employee_1/
│   │       ├── sample_0.jpg
│   │       ├── sample_1.jpg
│   │       └── ...
│   └── face_attendance.log            # Logs (auto-created)
│
├── addons/
│   └── face_attendance/
│       ├── __manifest__.py
│       ├── __init__.py
│       ├── controllers/
│       │   ├── __init__.py
│       │   └── face_attendance_controller.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── hr_employee_extend.py
│       │   └── face_attendance_log.py
│       ├── security/
│       │   └── ir.model.access.csv
│       ├── views/
│       │   ├── hr_employee_extend_views.xml
│       │   ├── face_attendance_log_views.xml
│       │   └── menu.xml
│
└── INSTALLATION_GUIDE.md
"""

# ============================================================================
# API REFERENCE
# ============================================================================

"""
POST /api/face_attendance/checkin
├─ Authentication: X-API-Key header
├─ Request Body:
│  {
│    "employee_id": 1,
│    "timestamp": "2024-01-15T10:30:45",
│    "confidence": 0.95,
│    "distance": 0.35,
│    "camera_source": "webcam_main",
│    "image_base64": "..." (optional)
│  }
└─ Response:
   {
     "status": "success",
     "message": "...",
     "data": {
       "log_id": 100,
       "employee_id": 1,
       "check_type": "check_in",
       "confidence": 0.95,
       "attendance_info": {...}
     }
   }

GET /api/face_attendance/employee/<id>
├─ Authentication: X-API-Key header
└─ Response:
   {
     "status": "success",
     "data": {
       "id": 1,
       "name": "John Doe",
       "department": "HR",
       "is_face_registered": true
     }
   }

GET /api/face_attendance/logs?limit=10&employee_id=1
├─ Authentication: X-API-Key header
└─ Response:
   {
     "status": "success",
     "total": 10,
     "data": [...]
   }

GET /api/face_attendance/health
└─ No authentication required
"""

# ============================================================================
# TROUBLESHOOTING CHECKLIST
# ============================================================================

"""
❌ "ImportError: No module named 'cv2'"
✓ Solution: pip install opencv-python

❌ "ImportError: No module named 'face_recognition'"
✓ Solution: pip install face_recognition
✓ Note: May take 5-10 minutes to install

❌ "Cannot connect to http://localhost:8069"
✓ Solution: Make sure Odoo is running
   $ ps aux | grep odoo

❌ "Invalid X-API-Key"
✓ Solution: Update API key in config or controller

❌ "Employee not found"
✓ Solution: Use correct employee ID from Odoo HR

❌ "Confidence too low"
✓ Solution: 
   - Improve lighting
   - Get closer to camera (30-50cm)
   - Look directly at camera
   - Re-register with more samples

❌ "Webcam not opening"
✓ Solution:
   - Check: ls /dev/video*
   - Grant permission: sudo usermod -a -G video $USER
   - Logout and login again
"""

# ============================================================================
# EXAMPLE WORKFLOW
# ============================================================================

"""
🎬 COMPLETE WORKFLOW:

DAY 1 - SETUP:
─────────────
09:00 - Start Odoo
09:05 - Create 5 test employees in Odoo HR
10:00 - Start AI Service
10:05 - Register employee faces:
         Menu 1 → ID 1 → Chụp 10 ảnh → ESC
         Menu 1 → ID 2 → Chụp 10 ảnh → ESC
         ... (for employees 3, 4, 5)
10:30 - Check: Menu 3 → See 5 employees registered

DAY 2 - TESTING:
────────────────
08:00 - Start Odoo
08:10 - Start AI Service
08:15 - Run webcam: Menu 2
08:20 - Employee 1 walks to camera → Auto check-in ✓
08:21 - Check Odoo: HR → Face Attendance Logs ✓
12:00 - Employee 1 walks to camera again → Check-out ✓
12:01 - Verify check-out in Odoo ✓

DAY 3 - PRODUCTION:
──────────────────
Keep AI Service running 24/7
- Employee check-ins automatically
- Logs recorded in Odoo
- HR team views dashboard
"""

# ============================================================================
# ADVANCED CONFIGURATION
# ============================================================================

"""
🔧 TUNE PERFORMANCE:

1. Face Detection Model:
   model='hog'  # Fast (default)
   model='cnn'  # Accurate but slow

2. Confidence Thresholds:
   0.3-0.4: Very sensitive (false positives)
   0.5-0.6: Balanced (recommended)
   0.7-0.9: Strict (false negatives)

3. Camera Settings:
   cv2.VideoCapture(0)    # Webcam 1
   cv2.VideoCapture(1)    # Webcam 2
   cv2.VideoCapture("rtsp://...") # IP Camera

4. Database Optimization:
   - Vacuum: VACUUM face_attendance_log;
   - Index: CREATE INDEX ON face_attendance_log (employee_id, check_time);
"""

# ============================================================================
# SECURITY CONSIDERATIONS
# ============================================================================

"""
🔐 SECURITY CHECKLIST:

[ ] API Key Management:
    - Store API key in environment variables
    - Rotate keys regularly
    - Never commit keys to git

[ ] Access Control:
    - Only HR team can view logs
    - Employees can only see their own records

[ ] Data Privacy:
    - Encrypt face_encoding in database
    - Don't expose face images publicly
    - GDPR compliance for employee data

[ ] Network Security:
    - Use HTTPS in production (not HTTP)
    - Enable SSL certificate
    - Use VPN for AI service connection

[ ] Audit Logging:
    - Log all API requests
    - Track who modified records
    - Keep access logs for 30 days
"""

# ============================================================================
# MONITORING & MAINTENANCE
# ============================================================================

"""
📊 MONITORING:

Daily Checks:
  1. AI Service running? → Check process
  2. Logs created? → Check database
  3. Sync successful? → Check attendance records
  4. Errors in logs? → Review face_attendance.log

Weekly Maintenance:
  1. Backup database
  2. Review flagged logs
  3. Retrain low-accuracy employees
  4. Check disk space for images

Monthly Tasks:
  1. Performance review
  2. Update models (if needed)
  3. Security audit
  4. Optimize database
"""

# ============================================================================
# NEXT STEPS
# ============================================================================

"""
📈 FUTURE ENHANCEMENTS:

Phase 2:
  - Mobile app for check-in
  - Multiple camera support
  - On-premises cloud backup
  - Advanced reporting dashboard

Phase 3:
  - Multi-modal authentication (face + PIN)
  - Real-time location tracking
  - Integration with payroll
  - ML model improvement with new data

Phase 4:
  - Edge computing (on-device inference)
  - 3D liveness detection
  - Spoofing detection
  - Cross-platform deployment
"""

print(__doc__)
