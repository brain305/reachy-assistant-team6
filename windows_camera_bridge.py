"""Windows에서 실행하는 웹캠 브리지 (WSL 프로세스에서 호출 가능).

Windows PowerShell:
  python windows_camera_bridge.py
WSL에서는 REACHY_CAMERA_SOURCE=bridge, REACHY_CAMERA_BRIDGE_URL 및 TOKEN 설정.
브리지는 신뢰할 수 있는 사설 네트워크에서만 사용하고 절대로 인터넷에 공개하지 마세요.
"""

import os
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
from dotenv import load_dotenv

load_dotenv()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.getenv("REACHY_CAMERA_BRIDGE_TOKEN", "")
        if not token or not hmac.compare_digest(self.headers.get("X-Camera-Token", ""), token):
            self.send_error(403)
            return
        if self.path != "/capture":
            self.send_error(404)
            return
        index = int(os.getenv("REACHY_CAMERA_INDEX", "0"))
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not camera.isOpened():
            camera.release()
            self.send_error(503, "Cannot open webcam")
            return
        try:
            ok, frame = camera.read()
            if not ok:
                self.send_error(503, "Cannot capture frame")
                return
            ok, data = cv2.imencode(".jpg", frame)
            if not ok:
                self.send_error(503, "JPEG encode failed")
                return
            payload = data.tobytes()
        finally:
            camera.release()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def main():
    if not os.getenv("REACHY_CAMERA_BRIDGE_TOKEN", ""):
        raise RuntimeError(".env에 REACHY_CAMERA_BRIDGE_TOKEN을 먼저 설정하세요.")
    host = os.getenv("REACHY_CAMERA_BRIDGE_BIND", "127.0.0.1")
    port = int(os.getenv("REACHY_CAMERA_BRIDGE_PORT", "8765"))
    print(f"Camera bridge listening on {host}:{port} (Ctrl+C 종료)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
