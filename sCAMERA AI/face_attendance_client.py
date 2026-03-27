#!/usr/bin/env python3
"""
Script nhận diện khuôn mặt chấm công — chạy ngoài Odoo
=====================================================
Lấy face encoding từ Odoo DB qua XML-RPC, mở webcam,
nhận diện real-time, gọi API /api/face_attendance/checkin.

Cách dùng:
    python face_attendance_client.py
    python face_attendance_client.py --odoo-url http://localhost:8069 --db ttdn-1713-n8
    python face_attendance_client.py --user admin --password admin

Phím tắt trong cửa sổ webcam:
    ESC / Q     Thoát
    R           Reload lại face encodings từ Odoo

Hành vi tự động:
    Khi nhận diện đúng và chấm công API trả thành công,
    chương trình sẽ hiển thị thông báo rồi tự tắt.
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
import xmlrpc.client
from datetime import datetime
from typing import Optional

import cv2
import face_recognition
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:  # pragma: no cover - optional desktop UI dependency
    tk = None
    ttk = None
    messagebox = None

# ============================================================================
# CONFIG MẶC ĐỊNH
# ============================================================================
DEFAULT_URL      = "http://localhost:8069"
DEFAULT_DB       = "ttdn-1713-n8"
DEFAULT_USER     = "admin"
DEFAULT_PASSWORD = "admin"

DISTANCE_THRESHOLD = 0.55     # khoảng cách Euclidean tối đa để chấp nhận match
COOLDOWN_SECONDS   = 10       # giây cooldown giữa 2 lần chấm công cùng người
RESIZE_SCALE       = 0.5      # thu nhỏ frame để nhận diện nhanh hơn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_STARTUP_DELAY = 3.0
DEFAULT_CLOSE_DELAY = 2.0
DEFAULT_UNICODE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def put_text_vn(
    frame: np.ndarray,
    text: str,
    org: tuple[int, int],
    font_size: int = 20,
    color: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """Vẽ text Unicode tiếng Việt lên frame bằng Pillow (fallback sang cv2 nếu lỗi)."""
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        draw = ImageDraw.Draw(pil_img)

        if os.path.exists(DEFAULT_UNICODE_FONT):
            font = ImageFont.truetype(DEFAULT_UNICODE_FONT, font_size)
        else:
            font = ImageFont.load_default()

        draw.text(org, text, font=font, fill=(color[2], color[1], color[0]))
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        cv2.putText(
            frame,
            text.encode("ascii", errors="ignore").decode("ascii"),
            org,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            1,
        )
        return frame


# ============================================================================
# ẢNH INPUT HELPER
# ============================================================================
def to_rgb_uint8(image: np.ndarray) -> np.ndarray:
    """Chuẩn hóa ảnh về RGB uint8, contiguous để face_recognition xử lý ổn định."""
    if image is None:
        raise ValueError("image is None")

    if image.ndim == 2:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.ndim == 3 and image.shape[2] == 4:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    elif image.ndim == 3 and image.shape[2] == 3:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")

    # Một số camera trả frame không phải uint8 (vd: 16-bit). Ép về uint8.
    if rgb.dtype != np.uint8:
        rgb = cv2.convertScaleAbs(rgb)

    # dlib yêu cầu buffer contiguous
    return np.ascontiguousarray(rgb)


# ========= ===================================================================
# LẤY ENCODINGS TỪ ODOO
# ============================================================================
def fetch_encodings_from_odoo(url: str, db: str, user: str, password: str) -> dict:
    """
    Trả về dict: {employee_code: {"name": ..., "encoding": np.array}}
    Lấy từ model hr.employee (nhan_vien) trường face_encoding (JSON text).
    """
    logger.info(f"Kết nối Odoo {url}, db={db}, user={user} ...")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise RuntimeError(f"Xác thực Odoo thất bại (db={db}, user={user})")
    logger.info(f"Đăng nhập thành công, uid={uid}")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    # Lấy tất cả nhân viên có face_encoding từ model nhan_vien
    employees = models.execute_kw(
        db, uid, password,
        "nhan_vien", "search_read",
        [[["face_encoding", "!=", False]]],
        {"fields": ["ho_va_ten", "ma_dinh_danh", "face_encoding"],
         "limit": 500},
    )

    result = {}
    skipped = 0
    for emp in employees:
        try:
            raw = emp.get("face_encoding") or ""
            if not raw:
                skipped += 1
                continue
            encoding_list = json.loads(raw)
            encoding = np.array(encoding_list, dtype=np.float64)
            # Bỏ vector không hợp lệ
            if encoding.shape != (128,):
                skipped += 1
                continue
            emp_code = emp.get("ma_dinh_danh") or str(emp["id"])
            result[emp_code] = {
                "name": emp.get("ho_va_ten") or emp_code,
                "encoding": encoding,
            }
        except Exception as exc:
            logger.warning(f"Bỏ qua nhân viên {emp.get('name')}: {exc}")
            skipped += 1

    logger.info(f"Tải xong {len(result)} nhân viên (bỏ qua {skipped})")
    return result


def fetch_employee_list(url: str, db: str, user: str, password: str) -> list[dict]:
    """Lấy danh sách nhân viên từ model nhan_vien để hiển thị trên màn hình Settings."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise RuntimeError(f"Xác thực Odoo thất bại (db={db}, user={user})")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    employees = models.execute_kw(
        db,
        uid,
        password,
        "nhan_vien",
        "search_read",
        [[]],
        {
            "fields": ["id", "ma_dinh_danh", "ho_va_ten"],
            "order": "ho_va_ten asc",
            "limit": 2000,
        },
    )
    return employees


def capture_face_photo() -> Optional[np.ndarray]:
    """Mở camera để chụp ảnh khuôn mặt. C để chụp, ESC/Q để hủy."""
    cap = None
    for cam_idx in (0, 1, 2):
        c = cv2.VideoCapture(cam_idx)
        if c.isOpened():
            cap = c
            logger.info(f"Mở webcam index {cam_idx} cho chế độ cập nhật FaceID")
            break
        c.release()

    if cap is None:
        return None

    captured = None
    window_name = "Capture Face - C: Chup | ESC/Q: Huy"
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        preview = frame.copy()
        cv2.putText(
            preview,
            "Can giua khuon mat trong khung, nhan C de chup",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            preview,
            "ESC/Q: Huy",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 200, 255),
            2,
        )
        cv2.imshow(window_name, preview)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("c"), ord("C")):
            captured = frame
            break
        if key in (27, ord("q"), ord("Q")):
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured


def update_employee_face_image(
    url: str,
    db: str,
    user: str,
    password: str,
    employee_id: int,
    image_bgr: np.ndarray,
) -> str:
    """Ghi ảnh vào trường `anh` và cố gắng tạo face encoding ngay sau đó."""
    ok, jpg = cv2.imencode(".jpg", image_bgr)
    if not ok:
        raise RuntimeError("Không mã hóa được ảnh chụp")
    image_b64 = base64.b64encode(jpg.tobytes()).decode("ascii")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise RuntimeError(f"Xác thực Odoo thất bại (db={db}, user={user})")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    wrote = models.execute_kw(
        db,
        uid,
        password,
        "nhan_vien",
        "write",
        [[employee_id], {"anh": image_b64}],
    )
    if not wrote:
        raise RuntimeError("Ghi ảnh lên nhân viên thất bại")

    # Gọi explicit để đảm bảo cập nhật face encoding ngay.
    encoding_msg = ""
    try:
        models.execute_kw(
            db,
            uid,
            password,
            "nhan_vien",
            "action_generate_face_encoding",
            [[employee_id]],
        )
        encoding_msg = " | FaceID đã được cập nhật"
    except Exception as exc:
        encoding_msg = f" | Đã lưu ảnh, nhưng tạo FaceID báo lỗi: {exc}"

    return f"Cập nhật ảnh thành công cho nhân viên ID {employee_id}{encoding_msg}"


def launch_settings_screen(args):
    """Màn hình Settings riêng: chọn/nhập nhân viên, chụp ảnh và cập nhật FaceID."""
    if tk is None or ttk is None or messagebox is None:
        raise RuntimeError("Python tkinter chưa sẵn sàng. Hãy cài gói tkinter của hệ điều hành.")

    root = tk.Tk()
    root.title("Face Attendance Settings")
    root.geometry("760x420")
    root.resizable(False, False)

    url_var = tk.StringVar(value=args.url)
    db_var = tk.StringVar(value=args.db)
    user_var = tk.StringVar(value=args.user)
    pass_var = tk.StringVar(value=args.password)
    emp_input_var = tk.StringVar(value="")
    selected_emp_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="Sẵn sàng")

    employee_rows: list[dict] = []
    employee_display_to_id: dict[str, int] = {}

    container = ttk.Frame(root, padding=12)
    container.pack(fill="both", expand=True)

    creds = ttk.LabelFrame(container, text="Kết nối Odoo", padding=10)
    creds.pack(fill="x")

    ttk.Label(creds, text="URL").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(creds, textvariable=url_var, width=42).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(creds, text="DB").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(creds, textvariable=db_var, width=20).grid(row=0, column=3, sticky="w", pady=4)

    ttk.Label(creds, text="User").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(creds, textvariable=user_var, width=42).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(creds, text="Password").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(creds, textvariable=pass_var, width=20, show="*").grid(row=1, column=3, sticky="w", pady=4)

    target = ttk.LabelFrame(container, text="Cập nhật khuôn mặt nhân viên", padding=10)
    target.pack(fill="x", pady=(12, 0))

    ttk.Label(target, text="Chọn nhân viên").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    emp_combo = ttk.Combobox(target, textvariable=selected_emp_var, width=78, state="readonly")
    emp_combo.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)

    ttk.Label(target, text="Hoặc nhập ID/Mã").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(target, textvariable=emp_input_var, width=35).grid(row=1, column=1, sticky="w", pady=4)

    def set_status(msg: str):
        status_var.set(msg)
        root.update_idletasks()

    def load_employees():
        nonlocal employee_rows, employee_display_to_id
        try:
            set_status("Đang tải danh sách nhân viên...")
            employee_rows = fetch_employee_list(
                url_var.get().strip(),
                db_var.get().strip(),
                user_var.get().strip(),
                pass_var.get(),
            )
            employee_display_to_id = {}
            items = []
            for row in employee_rows:
                emp_id = row.get("id")
                code = row.get("ma_dinh_danh") or ""
                name = row.get("ho_va_ten") or "(không tên)"
                display = f"{code} - {name} (ID:{emp_id})" if code else f"{name} (ID:{emp_id})"
                employee_display_to_id[display] = emp_id
                items.append(display)

            emp_combo["values"] = items
            if items:
                selected_emp_var.set(items[0])
            set_status(f"Tải xong {len(items)} nhân viên")
        except Exception as exc:
            set_status("Tải danh sách thất bại")
            messagebox.showerror("Lỗi", f"Không tải được danh sách nhân viên:\n{exc}")

    def resolve_employee_id() -> Optional[int]:
        raw = emp_input_var.get().strip()
        if raw:
            if raw.isdigit():
                return int(raw)
            for row in employee_rows:
                code = str(row.get("ma_dinh_danh") or "").strip().lower()
                if code and code == raw.lower():
                    return int(row.get("id"))
            return None

        selected = selected_emp_var.get().strip()
        return employee_display_to_id.get(selected)

    def capture_and_update():
        emp_id = resolve_employee_id()
        if not emp_id:
            messagebox.showwarning("Thiếu thông tin", "Hãy chọn nhân viên hoặc nhập đúng ID/Mã nhân viên.")
            return

        set_status(f"Mở camera để chụp ảnh cho nhân viên ID {emp_id}...")
        frame = capture_face_photo()
        if frame is None:
            set_status("Hủy chụp ảnh hoặc không mở được camera")
            return

        set_status("Đang cập nhật ảnh khuôn mặt lên Odoo...")
        try:
            msg = update_employee_face_image(
                url_var.get().strip(),
                db_var.get().strip(),
                user_var.get().strip(),
                pass_var.get(),
                emp_id,
                frame,
            )
            set_status("Cập nhật thành công")
            messagebox.showinfo("Thành công", msg)
        except Exception as exc:
            set_status("Cập nhật thất bại")
            messagebox.showerror("Lỗi", f"Không cập nhật được khuôn mặt:\n{exc}")

    actions = ttk.Frame(target)
    actions.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
    ttk.Button(actions, text="Tải danh sách nhân viên", command=load_employees).pack(side="left")
    ttk.Button(actions, text="Chụp ảnh và cập nhật khuôn mặt", command=capture_and_update).pack(side="left", padx=(10, 0))

    status_frame = ttk.LabelFrame(container, text="Trạng thái", padding=10)
    status_frame.pack(fill="x", pady=(12, 0))
    ttk.Label(status_frame, textvariable=status_var, foreground="#0b5394").pack(anchor="w")

    hint = (
        "Gợi ý: nhập mã nhân viên (ma_dinh_danh) hoặc chọn từ danh sách. "
        "Khi mở camera: nhấn C để chụp, ESC/Q để hủy."
    )
    ttk.Label(container, text=hint, foreground="#666666", wraplength=720).pack(anchor="w", pady=(10, 0))

    load_employees()
    root.mainloop()


# ============================================================================
# GỌI API CHẤM CÔNG
# ============================================================================
def call_checkin_api(
    url: str,
    employee_code: str,
    confidence: float,
    distance: float | None = None,
    timestamp: str | None = None,
) -> tuple[str, bool]:
    """Gọi /api/face_attendance/checkin, trả về (thông điệp hiển thị, có_thành_công)."""
    endpoint = f"{url}/api/face_attendance/checkin"
    payload = {
        "params": {
            "employee_code": employee_code,
            "timestamp": timestamp or datetime.now().isoformat(),
            "confidence": round(confidence, 4),
            "camera_source": "face_attendance_client",
            "distance": round(distance, 4) if distance is not None else None,
        }
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=8)
        resp.raise_for_status()
        body = resp.json()
        result = body.get("result") or body
        status_raw = str(result.get("status", "?") or "?")
        status = status_raw.lower()
        message = str(result.get("message", "") or "")
        message_lower = message.lower()
        emp_name = result.get("employee_name", "")
        check_type = result.get("check_type", "")

        success_statuses = {
            "success",
            "check_in",
            "check_out",
            "checked_in",
            "checked_out",
            "ok",
            "done",
            "already_checked_in",
            "already_checked_out",
        }
        duplicate_markers = (
            "duplicate check-in",
            "duplicate check-out",
            "duplicate attendance",
            "within 5 minutes",
            "already checked in",
            "already checked out",
        )
        is_duplicate_warning = status == "warning" and any(
            marker in message_lower for marker in duplicate_markers
        )
        is_success = status in success_statuses or is_duplicate_warning

        if is_success:
            if is_duplicate_warning:
                return (f"OK: {emp_name} | duplicate | {message}", True)
            return (f"OK: {emp_name} | {check_type} | {message}", True)
        return (f"[{status_raw}] {message}", False)
    except Exception as exc:
        return (f"Loi API: {exc}", False)


def run_quick_demo(args):
    """Demo nhanh: gọi API trực tiếp theo tham số CLI, không cần mở webcam."""
    if not args.demo_employee_code:
        raise ValueError("Thiếu --demo-employee-code")

    logger.info(
        "Demo nhanh với employee_code=%s confidence=%.4f distance=%.4f",
        args.demo_employee_code,
        args.demo_confidence,
        args.demo_distance,
    )
    msg, ok = call_checkin_api(
        args.url,
        args.demo_employee_code,
        args.demo_confidence,
        args.demo_distance,
        args.demo_timestamp,
    )
    status = "THÀNH CÔNG" if ok else "THẤT BẠI"
    logger.info("Kết quả demo nhanh [%s]: %s", status, msg)


# ============================================================================
# CHẾ ĐỘ ẢNH (không cần webcam)
# ============================================================================
def run_image(args):
    """Nhận diện khuôn mặt từ 1 hoặc nhiều file ảnh, không cần webcam."""
    known = fetch_encodings_from_odoo(args.url, args.db, args.user, args.password)
    if not known:
        logger.error("Không có nhân viên nào có face encoding trong Odoo. Dừng.")
        sys.exit(1)

    known_codes     = list(known.keys())
    known_encodings = np.array([known[c]["encoding"] for c in known_codes])

    image_paths = args.image
    for img_path in image_paths:
        logger.info(f"--- Xử lý ảnh: {img_path} ---")
        frame = cv2.imread(img_path)
        if frame is None:
            logger.error(f"Không đọc được file: {img_path}")
            continue

        try:
            rgb = to_rgb_uint8(frame)
        except Exception as exc:
            logger.error(f"Ảnh không hợp lệ ({img_path}): {exc}")
            continue

        face_locs = face_recognition.face_locations(rgb, model="hog")
        face_encs = face_recognition.face_encodings(rgb, face_locs)

        if not face_encs:
            logger.warning("Không phát hiện khuôn mặt nào trong ảnh.")
            continue

        logger.info(f"Phát hiện {len(face_encs)} khuôn mặt.")
        for i, face_enc in enumerate(face_encs):
            distances = np.linalg.norm(known_encodings - face_enc, axis=1)
            best_idx  = int(np.argmin(distances))
            best_dist = float(distances[best_idx])

            if best_dist <= DISTANCE_THRESHOLD:
                emp_code   = known_codes[best_idx]
                name       = known[emp_code]["name"]
                confidence = 1.0 - (best_dist / DISTANCE_THRESHOLD)
                logger.info(f"  Mat {i+1}: MATCH {name} (code={emp_code}, confidence={confidence*100:.1f}%, dist={best_dist:.3f})")
                if not args.dry_run:
                    api_msg, _ = call_checkin_api(args.url, emp_code, confidence, best_dist)
                    logger.info(f"  API: {api_msg}")
                else:
                    logger.info("  [dry-run] Bo qua goi API.")
            else:
                logger.info(f"  Mat {i+1}: KHONG KHOP (dist={best_dist:.3f}, threshold={DISTANCE_THRESHOLD})")


# ============================================================================
# MAIN LOOP (webcam)
# ============================================================================
def run(args):
    # Lấy encodings lần đầu
    known = fetch_encodings_from_odoo(args.url, args.db, args.user, args.password)
    if not known:
        logger.error("Không có nhân viên nào có face encoding trong Odoo. Dừng.")
        sys.exit(1)

    known_codes     = list(known.keys())
    known_encodings = np.array([known[c]["encoding"] for c in known_codes])

    # Mở webcam
    for cam_idx in (0, 1, 2):
        cap = cv2.VideoCapture(cam_idx)
        if cap.isOpened():
            logger.info(f"Mở webcam index {cam_idx}")
            break
        cap.release()
    else:
        logger.error("Không mở được webcam nào (index 0,1,2)")
        sys.exit(1)

    # Trạng thái
    last_checkin: dict[str, float] = {}   # emp_code -> time.time()
    display_msg = ""
    display_until = 0.0
    display_color = (0, 255, 0)
    auto_exit_at = None

    logger.info("Webcam sẵn sàng. Nhấn ESC/Q thoát, R để reload encodings.")

    startup_until = time.time() + args.startup_delay

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Lỗi đọc webcam")
            break

        now = time.time()

        # Cho cửa sổ mở một khoảng trước khi bắt đầu nhận diện để demo ổn định.
        if now < startup_until:
            remaining = max(0.0, startup_until - now)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 44), (0, 0, 0), cv2.FILLED)
            frame = put_text_vn(
                frame,
                f"Đang khởi động camera... nhận diện sau {remaining:.1f}s",
                (8, 10),
                font_size=22,
                color=(0, 220, 255),
            )
            cv2.imshow("Face Attendance", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q'), ord('Q')):
                logger.info("Thoát.")
                break
            continue

        small = cv2.resize(frame, (0, 0), fx=RESIZE_SCALE, fy=RESIZE_SCALE)
        try:
            rgb_small = to_rgb_uint8(small)
        except Exception as exc:
            logger.error(f"Frame webcam không hợp lệ: {exc}")
            continue

        face_locs = face_recognition.face_locations(rgb_small, model="hog")
        face_encs = face_recognition.face_encodings(rgb_small, face_locs)

        for (top, right, bottom, left), face_enc in zip(face_locs, face_encs):
            # Tính khoảng cách với tất cả nhân viên
            distances = np.linalg.norm(known_encodings - face_enc, axis=1)
            best_idx = int(np.argmin(distances))
            best_dist = float(distances[best_idx])

            # Scale lại tọa độ
            scale = int(1 / RESIZE_SCALE)
            t, r, b, l = top * scale, right * scale, bottom * scale, left * scale

            if best_dist <= DISTANCE_THRESHOLD:
                emp_code = known_codes[best_idx]
                name = known[emp_code]["name"]
                confidence = 1.0 - (best_dist / DISTANCE_THRESHOLD)
                label = f"{name} ({confidence*100:.0f}%)"
                box_color = (0, 200, 0)

                # Chấm công nếu chưa trong cooldown
                since_last = now - last_checkin.get(emp_code, 0)
                if since_last >= COOLDOWN_SECONDS:
                    last_checkin[emp_code] = now
                    logger.info(f"Nhan dien: {name} (code={emp_code}, dist={best_dist:.3f})")
                    api_msg, api_success = call_checkin_api(args.url, emp_code, confidence, best_dist)
                    logger.info(f"API: {api_msg}")
                    if api_success:
                        display_msg = f"Nhận diện được {name} | Chấm công thành công | Đang tắt..."
                        display_until = now + args.close_delay
                        display_color = (0, 220, 0)
                        auto_exit_at = now + args.close_delay
                    else:
                        display_msg = f"{name}: {api_msg}"
                        display_until = now + 4
                        display_color = (0, 120, 255)
                else:
                    remaining = int(COOLDOWN_SECONDS - since_last)
                    display_msg = f"{name} (cooldown {remaining}s)"
                    display_until = now + 1
                    display_color = (200, 200, 0)
            else:
                label = f"? (dist={best_dist:.2f})"
                box_color = (0, 0, 220)

            cv2.rectangle(frame, (l, t), (r, b), box_color, 2)
            cv2.rectangle(frame, (l, b - 28), (r, b), box_color, cv2.FILLED)
            frame = put_text_vn(frame, label, (l + 4, b - 24), font_size=18, color=(255, 255, 255))

        # Hiển thị thông báo API phía trên frame
        if now < display_until:
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 0), cv2.FILLED)
            frame = put_text_vn(frame, display_msg, (8, 8), font_size=22, color=display_color)

        # Hướng dẫn phím
        h = frame.shape[0]
        frame = put_text_vn(
            frame,
            "ESC/Q: Thoát | R: Tải lại encodings",
            (8, h - 28),
            font_size=18,
            color=(180, 180, 180),
        )

        cv2.imshow("Face Attendance", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q'), ord('Q')):
            logger.info("Thoat.")
            break
        elif key in (ord('r'), ord('R')):
            logger.info("Reload encodings tu Odoo...")
            try:
                known = fetch_encodings_from_odoo(
                    args.url, args.db, args.user, args.password
                )
                known_codes     = list(known.keys())
                known_encodings = np.array([known[c]["encoding"] for c in known_codes])
                display_msg   = f"Reload xong: {len(known)} nhan vien"
                display_until = time.time() + 3
                display_color = (255, 200, 0)
            except Exception as exc:
                logger.error(f"Reload that bai: {exc}")

        # Tự thoát sau khi nhận diện + chấm công thành công
        if auto_exit_at and time.time() >= auto_exit_at:
            logger.info("Cham cong thanh cong. Tu dong tat chuong trinh.")
            break

    cap.release()
    cv2.destroyAllWindows()


# ============================================================================
# CLI
# ============================================================================
def main():
    global COOLDOWN_SECONDS
    parser = argparse.ArgumentParser(
        description="Nhan dien khuon mat cham cong - chay ngoai Odoo"
    )
    parser.add_argument("--url",      default=DEFAULT_URL,      help="URL Odoo (default: %(default)s)")
    parser.add_argument("--db",       default=DEFAULT_DB,       help="Ten database (default: %(default)s)")
    parser.add_argument("--user",     default=DEFAULT_USER,     help="Username Odoo (default: %(default)s)")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password Odoo")
    parser.add_argument("--cooldown", type=int, default=COOLDOWN_SECONDS,
                        help="Cooldown giua 2 lan cham cong cung nguoi, giay (default: %(default)s)")
    parser.add_argument("--image", nargs="+", metavar="FILE",
                        help="Nhan dien tu file anh thay vi webcam. Co the truyen nhieu file.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chi nhan dien, khong goi API cham cong (dung voi --image)")
    parser.add_argument("--settings", action="store_true",
                        help="Mo man hinh Settings de cap nhat khuon mat cho nhan vien")
    parser.add_argument("--startup-delay", type=float, default=DEFAULT_STARTUP_DELAY,
                        help="So giay mo cua so webcam truoc khi bat dau nhan dien (default: %(default)s)")
    parser.add_argument("--close-delay", type=float, default=DEFAULT_CLOSE_DELAY,
                        help="So giay cho roi tu dong dong sau khi cham cong thanh cong (default: %(default)s)")
    parser.add_argument("--demo-employee-code", default="",
                        help="Demo nhanh: goi API truc tiep theo ma nhan vien, khong can webcam")
    parser.add_argument("--demo-confidence", type=float, default=0.95,
                        help="Do tin cay gui API trong demo nhanh (default: %(default)s)")
    parser.add_argument("--demo-distance", type=float, default=0.10,
                        help="Khoang cach gui API trong demo nhanh (default: %(default)s)")
    parser.add_argument("--demo-timestamp", default="",
                        help="Timestamp demo nhanh (ISO), vd: 2026-03-27T16:30:00")
    args = parser.parse_args()

    COOLDOWN_SECONDS = args.cooldown

    if args.settings:
        launch_settings_screen(args)
    elif args.demo_employee_code:
        run_quick_demo(args)
    elif args.image:
        run_image(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
    
# Done project
