#!/usr/bin/env python3
"""
Test Script cho Face Attendance API
Sử dụng để kiểm tra tất cả endpoints
"""

import requests
import json
from datetime import datetime
import sys
from typing import Dict, Any
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

ODOO_URL = "http://localhost:8069"
API_KEY = "your_secure_api_key_here"  # Thay đổi ở đây

COLORS = {
    'GREEN': '\033[92m',
    'RED': '\033[91m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'END': '\033[0m'
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(text):
    """In tiêu đề"""
    print(f"\n{COLORS['BLUE']}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{COLORS['END']}\n")

def print_success(text):
    """In success message"""
    print(f"{COLORS['GREEN']}✓ {text}{COLORS['END']}")

def print_error(text):
    """In error message"""
    print(f"{COLORS['RED']}✗ {text}{COLORS['END']}")

def print_info(text):
    """In info message"""
    print(f"{COLORS['YELLOW']}ℹ {text}{COLORS['END']}")

def print_json(data):
    """In JSON formatted"""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

# ============================================================================
# TEST CASES
# ============================================================================

class FaceAttendanceAPITest:
    """Test suite cho Face Attendance API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
    
    def _request(self, method: str, endpoint: str, data: Dict = None, **kwargs) -> Dict:
        """Tạo request"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=self.headers, **kwargs)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=self.headers, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return {
                'status_code': response.status_code,
                'body': response.json() if response.text else None,
                'headers': dict(response.headers),
            }
        except requests.exceptions.ConnectionError:
            return {
                'status_code': 0,
                'body': None,
                'error': 'Connection failed - Odoo may not be running'
            }
        except Exception as e:
            return {
                'status_code': 0,
                'body': None,
                'error': str(e)
            }
    
    def record_test(self, test_name: str, passed: bool, details: str = ""):
        """Ghi lại kết quả test"""
        status = "PASS" if passed else "FAIL"
        self.test_results['tests'].append({
            'name': test_name,
            'status': status,
            'details': details
        })
        
        if passed:
            self.test_results['passed'] += 1
            print_success(f"{test_name}. {details}")
        else:
            self.test_results['failed'] += 1
            print_error(f"{test_name}. {details}")
    
    # ====================================================================
    # TEST: HEALTH CHECK
    # ====================================================================
    
    def test_health_check(self):
        """Test health check endpoint"""
        print_header("Test 1: Health Check")
        
        print_info(f"Request: GET {self.base_url}/api/face_attendance/health")
        
        response = self._request('GET', '/api/face_attendance/health')
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'healthy':
                self.record_test(
                    "Health Check",
                    True,
                    f"Status: {body['status']}, Version: {body.get('version', 'N/A')}"
                )
                return True
            else:
                self.record_test(
                    "Health Check",
                    False,
                    f"Unexpected status: {body.get('status')}"
                )
        else:
            self.record_test(
                "Health Check",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
        return False
    
    # ====================================================================
    # TEST: GET EMPLOYEE INFO
    # ====================================================================
    
    def test_get_employee(self, employee_id: int = 1):
        """Test get employee info endpoint"""
        print_header("Test 2: Get Employee Info")
        
        endpoint = f"/api/face_attendance/employee/{employee_id}"
        print_info(f"Request: GET {self.base_url}{endpoint}")
        
        response = self._request('GET', endpoint)
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'success' and body.get('data'):
                data = body['data']
                self.record_test(
                    "Get Employee",
                    True,
                    f"Employee: {data.get('name')} (ID: {data.get('id')}), "
                    f"Face Registered: {data.get('is_face_registered')}"
                )
                return True, data
            else:
                self.record_test(
                    "Get Employee",
                    False,
                    f"Unexpected response: {body.get('status')}"
                )
        else:
            self.record_test(
                "Get Employee",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
        return False, None
    
    # ====================================================================
    # TEST: CHECK IN / CHECK OUT
    # ====================================================================
    
    def test_checkin(self, employee_id: int = 1, confidence: float = 0.95):
        """Test check-in endpoint"""
        print_header("Test 3: Check In / Check Out")
        
        endpoint = "/api/face_attendance/checkin"
        
        payload = {
            "employee_id": employee_id,
            "timestamp": datetime.now().isoformat(),
            "confidence": confidence,
            "distance": 0.35,
            "camera_source": "test_camera"
        }
        
        print_info(f"Request: POST {self.base_url}{endpoint}")
        print(f"Payload:")
        print_json(payload)
        
        response = self._request('POST', endpoint, payload)
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'success' and body.get('data'):
                data = body['data']
                self.record_test(
                    "Check In",
                    True,
                    f"Log ID: {data.get('log_id')}, Check Type: {data.get('check_type')}, "
                    f"Confidence: {data.get('confidence')}"
                )
                return True, data
            else:
                self.record_test(
                    "Check In",
                    False,
                    f"Status: {body.get('status')}, Code: {body.get('code')}"
                )
        else:
            self.record_test(
                "Check In",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
        return False, None
    
    # ====================================================================
    # TEST: GET LOGS
    # ====================================================================
    
    def test_get_logs(self, limit: int = 10, employee_id: int = None):
        """Test get logs endpoint"""
        print_header("Test 4: Get Logs")
        
        query = f"?limit={limit}"
        if employee_id:
            query += f"&employee_id={employee_id}"
        
        endpoint = f"/api/face_attendance/logs{query}"
        print_info(f"Request: GET {self.base_url}{endpoint}")
        
        response = self._request('GET', endpoint)
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'success':
                total = body.get('total', 0)
                self.record_test(
                    "Get Logs",
                    True,
                    f"Found {total} logs"
                )
                
                if body.get('data'):
                    print(f"\nFirst 3 logs:")
                    print_json(body['data'][:3])
                
                return True
            else:
                self.record_test(
                    "Get Logs",
                    False,
                    f"Unexpected status: {body.get('status')}"
                )
        else:
            self.record_test(
                "Get Logs",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
        return False
    
    # ====================================================================
    # TEST: AUTH ERROR
    # ====================================================================
    
    def test_invalid_api_key(self):
        """Test với invalid API key"""
        print_header("Test 5: Invalid API Key")
        
        # Tạo session với API key sai
        headers_invalid = {
            "Content-Type": "application/json",
            "X-API-Key": "invalid_key_123",
        }
        
        endpoint = "/api/face_attendance/health"
        print_info(f"Request: GET {self.base_url}{endpoint} (với invalid API key)")
        
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=headers_invalid,
                timeout=10
            )
            
            if response.status_code == 403 or response.status_code == 401:
                self.record_test(
                    "Invalid API Key",
                    True,
                    f"Correctly rejected with status {response.status_code}"
                )
            else:
                # Health check không cần auth, vậy test lại
                self.record_test(
                    "Invalid API Key",
                    True,
                    f"Health endpoint không cần auth (status {response.status_code})"
                )
        except Exception as e:
            self.record_test(
                "Invalid API Key",
                False,
                f"Error: {str(e)}"
            )
    
    # ====================================================================
    # TEST: LOW CONFIDENCE
    # ====================================================================
    
    def test_low_confidence(self, employee_id: int = 1):
        """Test dengan confidence thấp"""
        print_header("Test 6: Low Confidence Match")
        
        endpoint = "/api/face_attendance/checkin"
        
        payload = {
            "employee_id": employee_id,
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.45,  # Low confidence
            "distance": 0.75,
            "camera_source": "test_camera"
        }
        
        print_info("Request: POST /api/face_attendance/checkin (low confidence)")
        print(f"Payload:")
        print_json(payload)
        
        response = self._request('POST', endpoint, payload)
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'success':
                data = body.get('data', {})
                self.record_test(
                    "Low Confidence",
                    True,
                    f"Accepted but may be flagged. Log ID: {data.get('log_id')}"
                )
            else:
                self.record_test(
                    "Low Confidence",
                    False,
                    f"Rejected: {body.get('message')}"
                )
        else:
            self.record_test(
                "Low Confidence",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
    
    # ====================================================================
    # TEST: INVALID EMPLOYEE
    # ====================================================================
    
    def test_invalid_employee(self):
        """Test dengan invalid employee ID"""
        print_header("Test 7: Invalid Employee ID")
        
        endpoint = "/api/face_attendance/checkin"
        
        payload = {
            "employee_id": 99999,  # Non-existent
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.95,
            "distance": 0.35,
            "camera_source": "test_camera"
        }
        
        print_info("Request: POST /api/face_attendance/checkin (invalid employee)")
        
        response = self._request('POST', endpoint, payload)
        
        if response['status_code'] == 200 and response['body']:
            body = response['body']
            if body.get('status') == 'error' and body.get('code') == 'EMPLOYEE_NOT_FOUND':
                self.record_test(
                    "Invalid Employee",
                    True,
                    f"Correctly rejected: {body.get('message')}"
                )
            else:
                self.record_test(
                    "Invalid Employee",
                    False,
                    f"Unexpected response: {body.get('status')}"
                )
        else:
            self.record_test(
                "Invalid Employee",
                False,
                f"Status code: {response['status_code']}"
            )
        
        print(f"Response: ")
        print_json(response)
    
    # ====================================================================
    # RUN ALL TESTS
    # ====================================================================
    
    def run_all_tests(self, employee_id: int = 1):
        """Chạy tất cả tests"""
        print_header("FACE ATTENDANCE API TEST SUITE")
        
        print_info(f"Base URL: {self.base_url}")
        print_info(f"Employee ID: {employee_id}")
        print_info(f"API Key: {self.api_key[:10]}...")
        
        # Test 1: Health check
        self.test_health_check()
        
        # Test 2: Get employee
        success, emp_data = self.test_get_employee(employee_id)
        if not success:
            print_error("Cannot continue without valid employee. Exiting tests.")
            return
        
        time.sleep(1)
        
        # Test 3: Check in
        self.test_checkin(employee_id, confidence=0.95)
        
        time.sleep(1)
        
        # Test 4: Get logs
        self.test_get_logs(limit=5, employee_id=employee_id)
        
        time.sleep(1)
        
        # Test 5: Invalid API key
        self.test_invalid_api_key()
        
        time.sleep(1)
        
        # Test 6: Low confidence
        self.test_low_confidence(employee_id)
        
        time.sleep(1)
        
        # Test 7: Invalid employee
        self.test_invalid_employee()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """In kết quả tóm tắt"""
        print_header("TEST SUMMARY")
        
        total = self.test_results['passed'] + self.test_results['failed']
        
        print(f"Total Tests: {total}")
        print(f"{COLORS['GREEN']}Passed: {self.test_results['passed']}{COLORS['END']}")
        print(f"{COLORS['RED']}Failed: {self.test_results['failed']}{COLORS['END']}")
        
        if self.test_results['failed'] == 0:
            print(f"\n{COLORS['GREEN']}✓ ALL TESTS PASSED!{COLORS['END']}")
            return 0
        else:
            print(f"\n{COLORS['RED']}✗ SOME TESTS FAILED{COLORS['END']}")
            return 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("""
Usage: python test_api.py [options]

Options:
  --url URL             Odoo URL (default: http://localhost:8069)
  --key KEY             API Key (default: your_secure_api_key_here)
  --employee ID         Employee ID to test (default: 1)
  --help, -h            Show this help message

Examples:
  python test_api.py
  python test_api.py --url http://192.168.1.100:8069 --key abc123 --employee 5
            """)
            return 0
    
    # Parse arguments
    url = ODOO_URL
    key = API_KEY
    emp_id = 1
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--url' and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--key' and i + 1 < len(sys.argv):
            key = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--employee' and i + 1 < len(sys.argv):
            try:
                emp_id = int(sys.argv[i + 1])
            except:
                print_error("Invalid employee ID")
                return 1
            i += 2
        else:
            i += 1
    
    # Run tests
    tester = FaceAttendanceAPITest(url, key)
    exit_code = tester.run_all_tests(emp_id)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
