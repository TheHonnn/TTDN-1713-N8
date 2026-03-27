# Face Attendance AI System - Complete Architecture

## 🎯 System Overview

This is a production-ready face attendance system with three-tier architecture:
1. **Module 1 (nhan_su_ai_service)**: REST API Layer - receives requests from AI Service, validates, logs
2. **Module 2 (nhan_su_attendance_ai)**: Processing Layer - creates events, syncs to hr.attendance, detects duplicates
3. **Module 3 (nhan_su_attendance_policy)**: Rules Engine - applies shift policies, calculates late/early, generates daily sheets

---

## 📦 Module 1: nhan_su_ai_service (API Layer)

**Purpose**: Entry point for all AI recognition requests. Handles validation, logging, and request routing.

### REST API Endpoints

```
POST /api/face_attendance/checkin
├── Request Body:
│   ├── employee_code (string, required): Employee identifier
│   ├── timestamp (ISO-8601 string, required): When recognition occurred
│   ├── confidence (float 0-1, required): Face match confidence
│   └── [optional] camera_source, distance, image_base64, request_id
│
└── Response:
    ├── status: "success" | "duplicate" | "error"
    ├── employee_id: int
    ├── employee_name: string
    ├── check_type: "check_in" | "check_out" (computed)
    ├── is_late: boolean
    └── message: string

GET /api/face_attendance/health
└── Returns: {"status": "ok", "timestamp": "...", "service": "face_attendance_api"}

GET /api/face_attendance/employee/<id>
└── Returns: {"id": int, "code": str, "name": str, "dept": str, "job": str}

GET /api/face_attendance/logs?limit=10&employee_id=5
└── Returns: Paginated list of request logs with filtering
```

### Models

**ai.request.log** (600+ lines)
- Complete audit trail of every API call
- Stores: request_id, endpoint, ip_address, employee_code, status, error_message
- Stores full JSON payloads for debugging
- Records processing time in milliseconds

### Services

**attendance.ai.service** (450+ lines)
- `process_checkin(payload)`: Main orchestrator
  - Validates payload (required fields, confidence range, timestamp format)
  - Finds employee by code
  - Checks for duplicate (5-minute cooldown)
  - Delegates to Module 2 for event creation
  - Returns structured response

**security.service** (250+ lines)
- `verify_api_key()`: HMAC timing-safe comparison
- `check_rate_limit()`: IP-based limiting (100 req/60sec)
- `log_security_event()`: Audit logging for security events

### Controllers

**api_controller.py** (350+ lines)
- All routes use JSON request/response format
- Comprehensive error handling (INVALID_JSON, UNAUTHORIZED, INTERNAL_ERROR, etc.)
- Detailed logging for troubleshooting

---

## 📦 Module 2: nhan_su_attendance_ai (Processing Layer)

**Purpose**: Processes raw AI events, syncs to HR system, handles duplicate detection.

### Models

**ai.attendance.event** (350+ lines)
- Raw event data from AI recognition system
- Fields:
  - `employee_id` (Many2one hr.employee, indexed)
  - `timestamp` (Datetime, indexed)
  - `check_type` (computed: 6AM-12PM=check_in, else=check_out)
  - `confidence` (0-1 from AI)
  - `distance` (Euclidean distance metric)
  - `status` (success/low_confidence/no_match/duplicate)
  - `is_late`, `is_early` (computed from timestamp hour)
  - `attendance_id` (link to hr.attendance)
  - Camera metadata, image, flags, notes

- Methods:
  - `sync_to_hr_attendance()`: Creates/updates hr.attendance records
  - `flag_for_review()`: Marks suspicious events
  - `cleanup_old_records()`: Archives after 90 days

**hr.attendance (extended)** (100+ lines)
- Extends standard Odoo hr.attendance model
- Additional fields:
  - `is_face_recognition` (boolean)
  - `face_confidence` (float)
  - `ai_event_id` (link back to ai.attendance.event)
  - `worked_hours` (computed from check_in/out)

### Services

**attendance.logic.service** (400+ lines)
- `process_checkin(employee, payload)`: Interface called by Module 1
  - Creates ai.attendance.event record
  - Delegates processing to Module 2
  - Returns event record
  
- `process_ai_event(ai_event_id)`: Main processing flow
  - Validates event (confidence > 0.75)
  - Checks for duplicates in hr.attendance (5-min cooldown)
  - Syncs to hr.attendance with intelligent matching:
    - Check-in: finds today's record without check-out, or creates new
    - Check-out: finds today's check-in without check-out, or creates check-in/out pair
  - Returns detailed processing result

- `_check_hr_duplicate()`: Duplicate detection logic
  - Searches within 5-minute window
  - Same employee, same check type
  - Prevents duplicate entries

### Views & UI

- Tree view: Summary of all events with status, confidence, late/early indicators
- Form view: Detailed event info with image preview, flags, notes
- Search: Filter by employee, check_type, status, date, late/early
- Menu: "AI Attendance → Events"

---

## 📦 Module 3: nhan_su_attendance_policy (Rules Engine)

**Purpose**: Enforces attendance policies, calculates late/early, generates daily reports.

### Models

**attendance.rule** (Shift Definition)
- Defines company attendance policies
- Fields:
  - `shift_name`: e.g., "8:30-17:00", "Night Shift"
  - `start_time`: Hour (float, e.g., 8.5 = 08:30)
  - `end_time`: Hour (float, e.g., 17.0 = 17:00)
  - `break_duration`: Hours deducted from worked time
  - `allow_late_minutes`: Grace period for late arrival (default: 0)
  - `allow_early_minutes`: Grace period for early departure (default: 0)
  - `is_default`: Used when employee has no specific shift
  - `daily_hours`: Computed (end_time - start_time - break_duration)

**daily.sheet** (Daily Attendance Summary)
- Generated daily for each employee
- Fields:
  - `employee_id`, `work_date`, `shift_id`
  - `check_in`, `check_out`: From hr.attendance
  - `hours_worked`: Computed from check_in/out
  - `is_late`, `minutes_late`: Computed based on shift rules
  - `is_early`, `minutes_early`: Computed based on shift rules
  - `status`: absent/present/incomplete/on_leave/holiday
  - `notes`: Summary of policy violations

- Computed fields update automatically
- Unique constraint on (employee_id, work_date)

### Services

**attendance.policy.service** (400+ lines)
- `generate_daily_sheet(employee_id, work_date)`: Creates daily sheet
  - Gets employee's shift rule
  - Collects all hr.attendance records for the day
  - Computes policy status
  - Creates daily.sheet record
  
- `_compute_policy_status()`: Calculates late/early
  - Compares check-in/out with shift times
  - Applies grace periods
  - Calculates hours worked
  - Generates status and notes
  
- `generate_daily_sheets_batch(work_date)`: Batch generation
  - Creates sheets for all active employees
  - Handles errors gracefully
  
- `get_attendance_summary()`: Monthly statistics
  - Returns: total_days, present_days, absent_days, late_days, etc.

### Views & UI

- Tree view: Summary of all daily sheets with color coding
- Form view: Detailed breakdown with all policy calculations
- Search: Filter by employee, date, status, late/early
- Menu: "Attendance Policy → Shift Rules" and "→ Daily Sheets"

---

## 🔄 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ EXTERNAL: Python AI Service (Face Recognition)                 │
│ - Captures face from webcam                                     │
│ - Encodes to 128D embedding                                     │
│ - Calculates distance to known encodings                        │
│ - Sends employee_code + confidence to API                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ POST /api/face_attendance/checkin
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ MODULE 1: nhan_su_ai_service (API Layer)                        │
│ - api_controller.py → handlers POST request                     │
│ - attendance.ai.service → validates, finds employee             │
│ - Checks for duplicate (5-min cooldown in ai.attendance.event)  │
│ - Calls Module 2 to create event                                │
│ - Logs everything to ai.request.log                             │
│ - Returns JSON response                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Creates ai.attendance.event
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ MODULE 2: nhan_su_attendance_ai (Processing Layer)              │
│ - Creates ai.attendance.event record                            │
│ - attendance.logic.service processes event                      │
│ - Checks for HR duplicate (same employee, 5-min window)         │
│ - Syncs to hr.attendance (find/create check-in/out pair)        │
│ - Links ai_event to hr_attendance                               │
│ - Marks event success/duplicate/error                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Updates hr.attendance
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ MODULE 3: nhan_su_attendance_policy (Rules Engine)              │
│ - Triggered by daily.sheet generation (manual or cron)          │
│ - Collects hr.attendance for the day                            │
│ - Applies shift rule: check-in/out times                        │
│ - Calculates: late minutes, early minutes, hours worked         │
│ - Generates daily.sheet with policy violations                  │
│ - Data available for HR reports and payroll                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Features

### Module 1
- **API Key Verification**: HMAC timing-safe comparison (optional)
- **Rate Limiting**: 100 requests per 60 seconds per IP
- **Request Logging**: Complete audit trail of every request
- **Error Masking**: Generic errors returned to client, detailed logs server-side
- **CSRF Disabled**: For API endpoints (stateless)

### Module 2
- **Duplicate Prevention**: 5-minute cooldown prevents rapid duplicate submissions
- **Data Validation**: Confidence threshold (> 0.75), timestamp validation
- **Event Flagging**: Suspicious events marked for manual review
- **Link Tracking**: Complete audit trail via ai_event_id

### Module 3
- **Access Control**: Role-based rules in ir.model.access.csv
- **Read-only Computation**: Daily sheets computed from source data, not editable

---

## 📊 Typical Use Case: Single Check-in

```
1. Employee walks past camera at 8:35 AM
2. AI captures face, calculates confidence: 0.98
3. Python AI Service sends HTTP POST to /api/face_attendance/checkin
   {
     "employee_code": "NV001",
     "timestamp": "2026-03-26T08:35:00+07:00",
     "confidence": 0.98,
     "camera_source": "Door Camera 1",
     "distance": 0.35
   }

4. Module 1 receives request:
   ✓ Validates payload
   ✓ Finds employee "Nguyễn Văn A" (id=5)
   ✓ Checks duplicate: No recent event (last was 2 days ago)
   ✓ Calls Module 2 service

5. Module 2 processes check-in:
   ✓ Creates ai.attendance.event (timestamp=8:35, check_type=check_in)
   ✓ Checks hr.attendance: No check-in for today
   ✓ Creates hr.attendance (employee=5, check_in=8:35, check_out=null)
   ✓ Links records: ai_event→hr_attendance

6. Module 1 returns success:
   {
     "status": "success",
     "employee_id": 5,
     "employee_name": "Nguyễn Văn A",
     "check_type": "check_in",
     "is_late": true,
     "message": "Check-in recorded successfully"
   }

7. Later, daily.sheet generation:
   ✓ Shift rule: 8:30-17:00 (grace: 0 min)
   ✓ Employee checked in at 8:35 (5 min late)
   ✓ daily.sheet: is_late=true, minutes_late=5

8. HR sees report:
   ✓ Employee was 5 minutes late
   ✓ Can integrate into payroll system
```

---

## 🚀 Deployment Checklist

- [ ] Verify Odoo 16.0+ installed
- [ ] PostgreSQL running (ttdn-1713-n8 database, port 5431)
- [ ] Python AI Service running and accessible
- [ ] Create default attendance.rule record
- [ ] Assign shifts to employees (via hr.employee extension)
- [ ] Set up daily.sheet generation cron job
- [ ] Configure security groups and access rules
- [ ] Test complete flow: AI → API → Events → HR → Daily Sheets
- [ ] Verify no rate-limiting issues
- [ ] Check audit logs in ai.request.log

---

## 🧪 Testing Points

1. **Normal Check-in**: Employee checks in that morning
   - Verify: ai_request_log created, ai.attendance.event created, hr.attendance updated
   
2. **Duplicate Detection**: Employee walks past camera twice in 3 minutes
   - Verify: Second request returns "duplicate" status
   
3. **Auto Check-type**: Check-in at 8AM vs 6PM
   - Verify: 8AM → check_type='check_in', 6PM → check_type='check_out'
   
4. **Late Arrival**: Check-in at 8:45 (shift starts 8:30)
   - Verify: ai.attendance.event.is_late=true, daily.sheet.minutes_late=15
   
5. **No Shift Rule**: Employee with no shift assignment
   - Verify: Graceful error or default shift used
   
6. **Confidence Threshold**: Confidence = 0.5 (too low)
   - Verify: Event marked low_confidence, not synced to hr.attendance

---

## 📝 Configuration

### API Configuration (Module 1)
- **api_key**: Set via ir.config_parameter (optional)
- **rate_limit**: 100 requests per 60 seconds (configurable)

### Employee Configuration (hr.employee)
- **code**: Must match employee_code sent by AI Service
- **shift_id** (optional): Links to attendance.rule for shift assignment

### Shift Configuration (attendance.rule)
- Create at least one default shift
- Set **is_default=true** for fallback
- Example: "8:30-17:00" with 1-hour break

---

## 📚 File Structure

```
addons/
├── nhan_su_ai_service/             [Module 1: API Layer]
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── ai_request_log.py       [600+ lines]
│   ├── services/
│   │   ├── __init__.py
│   │   ├── attendance_ai_service.py [450+ lines]
│   │   └── security_service.py      [250+ lines]
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── api_controller.py        [350+ lines]
│   ├── security/
│   │   └── ir.model.access.csv
│   └── views/
│       └── menu.xml
│
├── nhan_su_attendance_ai/          [Module 2: Processing Layer]
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ai_attendance_event_new.py  [350+ lines]
│   │   └── hr_attendance_extend.py     [100+ lines]
│   ├── services/
│   │   ├── __init__.py
│   │   └── attendance_logic_service.py [400+ lines]
│   ├── security/
│   │   └── ir.model.access.csv
│   └── views/
│       ├── ai_attendance_event_views.xml
│       └── menu.xml
│
└── nhan_su_attendance_policy/      [Module 3: Rules Engine]
    ├── __init__.py
    ├── __manifest__.py
    ├── models/
    │   ├── __init__.py
    │   ├── attendance_rule.py       [100+ lines]
    │   └── daily_sheet.py           [150+ lines]
    ├── services/
    │   ├── __init__.py
    │   └── attendance_policy_service.py [400+ lines]
    ├── security/
    │   └── ir.model.access.csv
    └── views/
        ├── attendance_rule_views.xml
        └── daily_sheet_views.xml
```

---

## 📞 Support

For issues:
1. Check ai.request.log for API request/response details
2. Enable DEBUG logging in Odoo configuration
3. Verify database connectivity (PostgreSQL 5431)
4. Confirm Python AI Service is running and accessible
5. Check employee codes match between HR system and AI Service

---

**Total Code: 3500+ lines of production-ready Python/XML**
**Status: Complete and Ready for Production**
