import argparse
import json
from datetime import datetime

import requests


def call_api(url, payload):
    response = requests.post(url, json=payload, timeout=10)
    return response.status_code, response.json()


def main():
    parser = argparse.ArgumentParser(description="Test API nhan dien khuon mat ")
    parser.add_argument("--employee-code", default="001", help="ma_dinh_danh cua nhan vien")
    parser.add_argument(
        "--employee-codes",
        default="",
        help="Danh sach ma_dinh_danh, cach nhau boi dau phay. Vi du: 001,002,003",
    )
    parser.add_argument("--camera-source", default="Camera Cong Chinh - Gia lap", help="Ten nguon camera")
    parser.add_argument("--confidence", type=float, default=0.99, help="Do tin cay gia lap (0..1)")
    parser.add_argument("--url", default="http://localhost:8069/api/face_attendance/checkin", help="Endpoint API")
    parser.add_argument("--timestamp", default=None, help="Thoi gian ISO, mac dinh la now")
    args = parser.parse_args()

    timestamp = args.timestamp or datetime.now().isoformat()

    batch_codes = [code.strip() for code in args.employee_codes.split(",") if code.strip()]
    employee_codes = batch_codes if batch_codes else [args.employee_code]

    print(f"POST {args.url}")
    print(f"So luong ma can test: {len(employee_codes)}")

    summary = []
    for idx, employee_code in enumerate(employee_codes, start=1):
        payload = {
            "params": {
                "employee_code": employee_code,
                "timestamp": timestamp,
                "camera_source": args.camera_source,
                "confidence": args.confidence,
            }
        }

        print("\n" + "=" * 70)
        print(f"[{idx}/{len(employee_codes)}] employee_code={employee_code}")
        print("Payload:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        try:
            status_code, body = call_api(args.url, payload)
            result = body.get("result", {}) if isinstance(body, dict) else {}
            status = result.get("status") or body.get("status")
            message = result.get("message") or body.get("message")

            print(f"HTTP {status_code}")
            print("Response:")
            print(json.dumps(body, ensure_ascii=False, indent=2))

            summary.append({
                "employee_code": employee_code,
                "http": status_code,
                "status": status,
                "message": message,
            })
        except requests.RequestException as exc:
            print(f"Khong the goi API: {exc}")
            summary.append({
                "employee_code": employee_code,
                "http": None,
                "status": "request_error",
                "message": str(exc),
            })

    print("\n" + "#" * 70)
    print("TONG KET")
    print("#" * 70)
    for item in summary:
        print(
            f"- {item['employee_code']}: "
            f"http={item['http']} status={item['status']} message={item['message']}"
        )


if __name__ == "__main__":
    main()