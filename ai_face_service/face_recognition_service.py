"""
Face Attendance Recognition Service
Sử dụng OpenCV + face_recognition để nhận diện khuôn mặt từ webcam
Và gọi API Odoo để chấm công tự động
"""

import cv2
import face_recognition
import numpy as np
import os
import pickle
import requests
import json
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, Tuple, Optional
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

ODOO_URL = "http://localhost:8069"
ODOO_API_KEY = "your_secure_api_key_here"  # Cần thay đổi
DATASET_PATH = "./face_dataset"  # Thư mục lưu encodings của nhân viên
ENCODINGS_FILE = os.path.join(DATASET_PATH, "encodings.pickle")
EMPLOYEE_MAPPING_FILE = os.path.join(DATASET_PATH, "employee_mapping.json")

CONFIDENCE_THRESHOLD = 0.55  # Face recognition confidence threshold
DISTANCE_THRESHOLD = 0.6  # Khoảng cách tối đa cho match

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('face_attendance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# SETUP & DATA PREPARATION
# ============================================================================

class FaceDatasetManager:
    """Quản lý dataset khuôn mặt nhân viên"""
    
    def __init__(self, dataset_path: str = DATASET_PATH):
        self.dataset_path = dataset_path
        self.encodings_file = os.path.join(dataset_path, "encodings.pickle")
        self.mapping_file = os.path.join(dataset_path, "employee_mapping.json")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Tạo thư mục nếu chưa tồn tại"""
        Path(self.dataset_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Dataset directory ready: {self.dataset_path}")

    @staticmethod
    def open_camera():
        """Try a small set of common webcam indices before failing."""
        for camera_index in (0, 1):
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                logger.info(f"✓ Mở webcam tại camera index {camera_index}")
                return cap
            cap.release()
        logger.error("Không thể mở webcam")
        return None
    
    def capture_face_for_employee(self, employee_id: int, num_samples: int = 10):
        """
        Chụp khuôn mặt nhân viên từ webcam + lưu encodings
        
        Args:
            employee_id: ID nhân viên trong Odoo
            num_samples: Số lượng ảnh để chụp (càng nhiều càng chính xác)
        """
        print(f"\n📸 Chụp ảnh cho nhân viên ID: {employee_id}")
        print(f"Nhấn SPACE để chụp, ESC để dừng")
        
        cap = self.open_camera()
        if not cap:
            return False
        
        captured_images = []
        samples_taken = 0
        employee_dir = os.path.join(self.dataset_path, f"employee_{employee_id}")
        Path(employee_dir).mkdir(parents=True, exist_ok=True)
        
        while samples_taken < num_samples:
            ret, frame = cap.read()
            if not ret:
                logger.error("Lỗi đọc webcam")
                break
            
            # Resize để xử lý nhanh hơn
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Detect khuôn mặt
            face_locations = face_recognition.face_locations(
                rgb_small_frame, 
                model='hog'  # 'cnn' chính xác hơn nhưng chậm
            )
            
            if face_locations:
                # Vẽ hộp quanh khuôn mặt
                for top, right, bottom, left in face_locations:
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                
                cv2.putText(frame, f"Samples: {samples_taken}/{num_samples}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "No face detected", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            cv2.imshow("Face Capture", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                logger.info(f"Dừng chụp ảnh cho nhân viên {employee_id}, lấy {samples_taken} ảnh")
                break
            elif key == 32 and face_locations:  # SPACE
                # Lưu ảnh và encoding
                img_path = os.path.join(employee_dir, f"sample_{samples_taken}.jpg")
                cv2.imwrite(img_path, frame)
                captured_images.append(frame)
                samples_taken += 1
                logger.info(f"✓ Chụp ảnh {samples_taken}/{num_samples}")
                time.sleep(0.5)  # Tránh chụp nhanh quá
        
        cap.release()
        cv2.destroyAllWindows()
        
        if captured_images:
            self._encode_and_save(employee_id, captured_images)
            return True
        return False
    
    def _encode_and_save(self, employee_id: int, images: list):
        """Encode khuôn mặt từ ảnh và lưu"""
        encodings = []
        
        for img in images:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_encodings = face_recognition.face_encodings(rgb_img)
            
            if face_encodings:
                encodings.extend(face_encodings)
        
        if encodings:
            # Lấy encoding trung bình (tăng độ chính xác)
            average_encoding = np.mean(encodings, axis=0)
            
            # Tải file encodings hiện tại
            all_encodings = {}
            if os.path.exists(self.encodings_file):
                with open(self.encodings_file, 'rb') as f:
                    all_encodings = pickle.load(f)
            
            # Lưu encoding
            all_encodings[str(employee_id)] = average_encoding.tolist()
            
            with open(self.encodings_file, 'wb') as f:
                pickle.dump(all_encodings, f)
            
            # Cập nhật mapping file
            mapping = {}
            if os.path.exists(self.mapping_file):
                with open(self.mapping_file, 'r') as f:
                    mapping = json.load(f)
            
            mapping[str(employee_id)] = {
                'employee_id': employee_id,
                'created_at': datetime.now().isoformat(),
                'samples': len(encodings)
            }
            
            with open(self.mapping_file, 'w') as f:
                json.dump(mapping, f, indent=2)
            
            logger.info(f"✓ Lưu encoding cho nhân viên {employee_id} ({len(encodings)} samples)")
        else:
            logger.warning(f"Không detect được khuôn mặt từ các ảnh")
    
    def load_encodings(self) -> Dict:
        """Tải encodings từ file"""
        if not os.path.exists(self.encodings_file):
            logger.warning("File encodings không tồn tại")
            return {}
        
        with open(self.encodings_file, 'rb') as f:
            encodings = pickle.load(f)
        
        # Convert list về numpy array
        for emp_id in encodings:
            encodings[emp_id] = np.array(encodings[emp_id])
        
        return encodings


# ============================================================================
# FACE RECOGNITION ENGINE
# ============================================================================

class FaceRecognitionEngine:
    """Engine nhận diện khuôn mặt real-time"""
    
    def __init__(self, encodings_file: str = ENCODINGS_FILE):
        self.encodings_file = encodings_file
        self.mapping_file = EMPLOYEE_MAPPING_FILE
        self.known_encodings = {}
        self.known_names = {}
        self.employee_mapping = {}
        self._load_known_faces()

    def _load_employee_mapping(self):
        if not os.path.exists(self.mapping_file):
            self.employee_mapping = {}
            return
        with open(self.mapping_file, 'r') as f:
            self.employee_mapping = json.load(f)
    
    def _load_known_faces(self):
        """Tải encodings từ file"""
        if not os.path.exists(self.encodings_file):
            logger.warning("Không tìm thấy file encodings")
            return

        self._load_employee_mapping()
        
        with open(self.encodings_file, 'rb') as f:
            data = pickle.load(f)
        
        for emp_id, encoding in data.items():
            self.known_encodings[emp_id] = np.array(encoding)
            mapping_entry = self.employee_mapping.get(emp_id, {})
            self.known_names[emp_id] = mapping_entry.get('name') or f"Employee {emp_id}"
        
        logger.info(f"✓ Tải {len(self.known_encodings)} nhân viên từ database")
    
    def recognize_face(self, frame) -> Tuple[Optional[str], float]:
        """
        Nhận diện khuôn mặt từ frame
        
        Returns:
            (employee_id, confidence) hoặc (None, 0.0) nếu không match
        """
        # Resize để xử lý nhanh
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_small_frame, model='hog')
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        if not face_encodings:
            return None, 0.0
        
        # Lấy encoding đầu tiên (nếu có nhiều mặt)
        face_encoding = face_encodings[0]
        
        # So sánh với các encoding đã lưu
        best_match_id = None
        best_distance = float('inf')
        
        for emp_id, known_encoding in self.known_encodings.items():
            # Tính khoảng cách Euclidean
            distance = np.linalg.norm(face_encoding - known_encoding)
            
            if distance < best_distance:
                best_distance = distance
                best_match_id = emp_id
        
        # Kiểm tra confidence
        if best_distance <= DISTANCE_THRESHOLD:
            confidence = 1 - (best_distance / DISTANCE_THRESHOLD)
            return str(best_match_id), confidence
        
        return None, 0.0
    
    def run_webcam(self, on_recognize_callback=None):
        """
        Chạy webcam real-time để nhận diện khuôn mặt
        
        Args:
            on_recognize_callback: Function được gọi khi nhận diện thành công
                                  Signature: callback(employee_id, confidence)
        """
        cap = FaceDatasetManager.open_camera()
        if not cap:
            return
        
        logger.info("🎥 Khởi động webcam (ESC để thoát)")
        
        last_recognized_id = None
        recognition_cooldown = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Lỗi đọc từ webcam")
                break
            
            # Nhận diện khuôn mặt
            employee_id, confidence = self.recognize_face(frame)
            
            # Vẽ UI
            h, w = frame.shape[:2]
            
            if employee_id is not None:
                display_name = self.known_names.get(employee_id, f"Employee {employee_id}")
                label = f"{display_name} ({confidence*100:.1f}%)"
                color = (0, 255, 0)  # Green
                
                # Tránh gọi API quá nhiều lần cho cùng 1 người
                if employee_id != last_recognized_id:
                    last_recognized_id = employee_id
                    recognition_cooldown = 30  # 30 frames = ~1 giây
                    
                    logger.info(f"✅ Nhận diện: {label}")
                    
                    if on_recognize_callback:
                        on_recognize_callback(employee_id, confidence)
            else:
                label = "No match"
                color = (0, 0, 255)  # Red
                if recognition_cooldown == 0:
                    last_recognized_id = None
            
            if recognition_cooldown > 0:
                recognition_cooldown -= 1
            
            # Vẽ text lên frame
            cv2.putText(frame, label, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, "ESC: Exit | SPACE: Capture | C: Clear", 
                       (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Face Attendance - Press ESC to exit", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                logger.info("🛑 Dừng webcam")
                break
        
        cap.release()
        cv2.destroyAllWindows()


# ============================================================================
# ODOO API INTEGRATION
# ============================================================================

class OdooAPIClient:
    """Kết nối với Odoo API để chấm công"""
    
    def __init__(self, odoo_url: str = ODOO_URL, api_key: str = ODOO_API_KEY):
        self.odoo_url = odoo_url
        self.api_key = api_key
        self.mapping_file = EMPLOYEE_MAPPING_FILE
        self.employee_mapping = self._load_employee_mapping()

    def _load_employee_mapping(self):
        if not os.path.exists(self.mapping_file):
            return {}
        with open(self.mapping_file, 'r') as f:
            return json.load(f)

    def _build_employee_payload(self, matched_identifier):
        mapping_entry = self.employee_mapping.get(str(matched_identifier), {})

        if mapping_entry.get('employee_code'):
            return {'employee_code': mapping_entry['employee_code']}

        if mapping_entry.get('employee_id'):
            return {'employee_id': mapping_entry['employee_id']}

        if str(matched_identifier).isdigit():
            return {'employee_id': int(matched_identifier)}

        return {'employee_code': str(matched_identifier)}
    
    def record_attendance(self, matched_identifier: str, confidence: float, camera_source: str = 'webcam_main') -> bool:
        """
        Gọi API Odoo để chấm công
        
        Args:
            employee_id: ID nhân viên
            
        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            endpoint = f"{self.odoo_url}/api/face_attendance/checkin"
            
            payload = self._build_employee_payload(matched_identifier)
            payload.update({
                "timestamp": datetime.now().isoformat(),
                "confidence": float(confidence),
                "camera_source": camera_source,
            })
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }
            
            logger.info(f"📤 Gửi request chấm công: payload={payload}")
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Chấm công thành công: {data}")
                return True
            else:
                logger.error(f"❌ Lỗi API: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Lỗi kết nối: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Lỗi: {e}")
            return False


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """
    Main function - giao diện dòng lệnh
    """
    print("\n" + "="*60)
    print("🤖 FACE ATTENDANCE RECOGNITION SERVICE")
    print("="*60)
    
    dataset_manager = FaceDatasetManager()
    odoo_client = OdooAPIClient()
    
    while True:
        print("\n📋 MENU:")
        print("1. 📸 Chụp ảnh + huấn luyện cho nhân viên")
        print("2. 🎥 Chạy webcam nhận diện (chấm công)")
        print("3. 📊 Hiển thị số nhân viên trong database")
        print("0. ❌ Thoát")
        
        choice = input("\nChọn (0-3): ").strip()
        
        if choice == '1':
            emp_id = input("Nhập ID nhân viên: ").strip()
            try:
                emp_id = int(emp_id)
                num_samples = input("Số lượng ảnh (mặc định 10): ").strip()
                num_samples = int(num_samples) if num_samples else 10
                
                dataset_manager.capture_face_for_employee(emp_id, num_samples)
            except ValueError:
                print("❌ ID không hợp lệ")
        
        elif choice == '2':
            print("\n🎥 Bắt đầu webcam...")
            engine = FaceRecognitionEngine()
            
            def on_face_recognized(emp_id, confidence):
                # Gọi API Odoo để chấm công
                odoo_client.record_attendance(emp_id, confidence)
            
            engine.run_webcam(on_recognize_callback=on_face_recognized)
        
        elif choice == '3':
            try:
                with open(dataset_manager.mapping_file, 'r') as f:
                    mapping = json.load(f)
                print(f"\n📊 Tổng cộng: {len(mapping)} nhân viên")
                for emp_id, info in mapping.items():
                    print(f"  - ID {emp_id}: {info['samples']} samples")
            except FileNotFoundError:
                print("❌ Chưa có dữ liệu")
        
        elif choice == '0':
            print("👋 Thoát")
            break
        
        else:
            print("❌ Lựa chọn không hợp lệ")


if __name__ == "__main__":
    main()
