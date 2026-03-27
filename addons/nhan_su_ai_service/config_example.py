"""
Configuration file cho Face Attendance System
Copy file này thành config.py và sửa các giá trị

DO NOT commit this file with real values to git!
Keep API keys in environment variables instead.
"""

import os

# ============================================================================
# ODOO CONFIGURATION
# ============================================================================

# Odoo server URL
ODOO_URL = os.environ.get('ODOO_URL', "http://localhost:8069")

# API Key for authentication
# IMPORTANT: Use environment variable in production!
ODOO_API_KEY = os.environ.get('ODOO_FACE_ATTENDANCE_API_KEY', "your_secure_api_key_here")

# Database name (optional, for direct connection)
ODOO_DB = "your_odoo_database"

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
# Lower = more lenient, Higher = stricter
CONFIDENCE_THRESHOLD = float(os.environ.get('FACE_CONFIDENCE_THRESHOLD', "0.55"))

# Distance threshold for face comparison (0-1)
# Lower = stricter matching, Higher = more lenient
DISTANCE_THRESHOLD = float(os.environ.get('FACE_DISTANCE_THRESHOLD', "0.6"))

# Face detection model: 'hog' (fast) or 'cnn' (accurate)
FACE_DETECTION_MODEL = os.environ.get('FACE_DETECTION_MODEL', "hog")

# Number of face samples to capture per employee
FACE_SAMPLES_COUNT = int(os.environ.get('FACE_SAMPLES_COUNT', "10"))

# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================

# Camera index (0 = default, 1 = secondary, etc. or IP camera URL)
CAMERA_INDEX = 0

# Camera resolution (width, height)
CAMERA_RESOLUTION = (640, 480)

# Webcam frame size multiplier (0.25 means 25% of original)
# Lower value = faster processing but less accurate
FRAME_SCALE = 0.25

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = os.environ.get('LOG_LEVEL', "INFO")

# Log file path
LOG_FILE = os.environ.get('LOG_FILE', "./face_attendance.log")

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

# Maximum face recognition logging
MAX_FACES_IN_FRAME = 1  # Only process first face

# Enable/disable auto-sync to hr.attendance
AUTO_SYNC_TO_ATTENDANCE = True

# ============================================================================
# DEVELOPMENT/PRODUCTION MODES
# ============================================================================

# True = development mode (verbose logging, no SSL verification)
# False = production mode (minimal logging, strict SSL)
DEBUG_MODE = os.environ.get('DEBUG_MODE', "False").lower() == "true"

# Disable SSL verification (not recommended for production)
DISABLE_SSL_VERIFY = os.environ.get('DISABLE_SSL_VERIFY', "False").lower() == "true"

# ============================================================================
# ADVANCED OPTIONS
# ============================================================================

# Enable detailed API logging
VERBOSE_API_LOGGING = os.environ.get('VERBOSE_API_LOGGING', "False").lower() == "true"

# Save face images from recognition (for debugging/auditing)
SAVE_FACE_SNAPSHOTS = os.environ.get('SAVE_FACE_SNAPSHOTS', "False").lower() == "true"

# Path to save snapshots
SNAPSHOTS_PATH = "./face_snapshots"

# Enable multi-face detection (if multiple people in frame)
ENABLE_MULTI_FACE = os.environ.get('ENABLE_MULTI_FACE', "False").lower() == "true"

# Enable liveness detection (prevent spoof with photos)
ENABLE_LIVENESS_DETECTION = os.environ.get('ENABLE_LIVENESS_DETECTION', "False").lower() == "true"

# ============================================================================
# EXAMPLE ENVIRONMENT VARIABLES (.env file)
# ============================================================================

"""
# .env file example

ODOO_URL=http://localhost:8069
ODOO_FACE_ATTENDANCE_API_KEY=abc123def456
FACE_DATASET_PATH=/var/lib/face_attendance/dataset
FACE_CONFIDENCE_THRESHOLD=0.55
FACE_DISTANCE_THRESHOLD=0.6
FACE_DETECTION_MODEL=hog
LOG_LEVEL=INFO
LOG_FILE=/var/log/face_attendance.log
DEBUG_MODE=False
DISABLE_SSL_VERIFY=False

Create .env file in project root, then load with:
  from dotenv import load_dotenv
  load_dotenv()
"""

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate configuration values"""
    errors = []
    
    # Validate thresholds
    if not 0 <= CONFIDENCE_THRESHOLD <= 1:
        errors.append("CONFIDENCE_THRESHOLD must be between 0 and 1")
    
    if not 0 <= DISTANCE_THRESHOLD <= 1:
        errors.append("DISTANCE_THRESHOLD must be between 0 and 1")
    
    # Validate model
    if FACE_DETECTION_MODEL not in ['hog', 'cnn']:
        errors.append("FACE_DETECTION_MODEL must be 'hog' or 'cnn'")
    
    # Validate log level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if LOG_LEVEL not in valid_levels:
        errors.append(f"LOG_LEVEL must be one of {valid_levels}")
    
    return errors


if __name__ == "__main__":
    # Print current configuration
    print("=" * 60)
    print("Face Attendance Configuration")
    print("=" * 60)
    print(f"\nOdoo:")
    print(f"  URL: {ODOO_URL}")
    print(f"  API Key: {ODOO_API_KEY[:10]}...")
    
    print(f"\nFace Recognition:")
    print(f"  Dataset Path: {DATASET_PATH}")
    print(f"  Confidence Threshold: {CONFIDENCE_THRESHOLD}")
    print(f"  Distance Threshold: {DISTANCE_THRESHOLD}")
    print(f"  Detection Model: {FACE_DETECTION_MODEL}")
    
    print(f"\nCamera:")
    print(f"  Index: {CAMERA_INDEX}")
    print(f"  Resolution: {CAMERA_RESOLUTION}")
    
    print(f"\nLogging:")
    print(f"  Level: {LOG_LEVEL}")
    print(f"  File: {LOG_FILE}")
    
    print(f"\nMode:")
    print(f"  Debug: {DEBUG_MODE}")
    
    # Validate
    errors = validate_config()
    if errors:
        print(f"\n❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"\n✓ Configuration is valid")
    
    print("\n" + "=" * 60)
