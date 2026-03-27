"""
Configuration file cho Face Attendance System
Tạo từ config_example.py - sửa cho match với Odoo hiện tại

DO NOT commit this file with real values to git!
"""

import os

# ============================================================================
# ODOO CONFIGURATION
# ============================================================================

# Odoo server URL
ODOO_URL = "http://localhost:8069"

# API Key for authentication
ODOO_API_KEY = "your_secure_api_key_here"  # Change this after Odoo setup

# Database name
ODOO_DB = "ttdn-1713-n8"

# ============================================================================
# FACE RECOGNITION CONFIGURATION
# ============================================================================

# Path to store face datasets
DATASET_PATH = os.environ.get('FACE_DATASET_PATH', "./face_dataset")

# File to store face encodings
ENCODINGS_FILE = os.path.join(DATASET_PATH, "encodings.pickle")

# File to store employee-to-encoding mapping
EMPLOYEE_MAPPING_FILE = os.path.join(DATASET_PATH, "employee_mapping.json")

# Confidence threshold (0-1)
CONFIDENCE_THRESHOLD = 0.55

# Distance threshold for face comparison (0-1)
DISTANCE_THRESHOLD = 0.6

# Face detection model: 'hog' (fast) or 'cnn' (accurate)
FACE_DETECTION_MODEL = "hog"

# Number of face samples to capture per employee
FACE_SAMPLES_COUNT = 10

# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================

# Camera index (0 = default webcam)
CAMERA_INDEX = 0

# Camera resolution (width, height)
CAMERA_RESOLUTION = (640, 480)

# Webcam frame size multiplier (0.25 = 25% = faster processing)
FRAME_SCALE = 0.25

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# Log file path
LOG_FILE = "./face_attendance.log"

# Log file max size (MB)
LOG_FILE_MAX_SIZE = 10

# Number of backup log files to keep
LOG_BACKUP_COUNT = 5

# ============================================================================
# REQUEST CONFIGURATION
# ============================================================================

# Request timeout (seconds)
REQUEST_TIMEOUT = 10

# Retry attempts for API calls
REQUEST_RETRY_ATTEMPTS = 3

# Retry delay (seconds)
REQUEST_RETRY_DELAY = 1

# ============================================================================
# SYSTEM BEHAVIOR
# ============================================================================

# Cooldown period between duplicate checks (seconds)
DUPLICATE_CHECK_COOLDOWN = 300  # 5 minutes
