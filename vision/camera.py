"""Windows, Linux/WSL 환경에 대응하는 이미지 입력.

환경변수 REACHY_CAMERA_SOURCE: auto | device | file | bridge
- device: Windows DirectShow / Linux V4L2(/dev/video*)
- file: REACHY_CAMERA_IMAGE에 지정된 JPEG/PNG
- bridge: Windows 호스트의 windows_camera_bridge.py를 통해 JPEG 획득
WSL에는 웹캠 장치 전달이 보장되지 않으므로 file/bridge 모드를 지원한다.
"""

import os
import platform
import time
from pathlib import Path
from urllib.parse import urlparse

import cv2
import requests


def _camera_device_bytes() -> bytes:
    index = int(os.getenv("REACHY_CAMERA_INDEX", "0"))
    if platform.system() == "Windows":
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif platform.system() == "Darwin":
        # macOS에는 V4L2가 없으므로 AVFoundation을 사용한다.
        camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    else:
        camera = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        if platform.system() == "Darwin":
            raise RuntimeError(
                f"카메라 장치 {index}를 열 수 없습니다. macOS 시스템 설정 → 개인정보 보호 및 보안 → 카메라에서 "
                "이 프로그램을 실행한 터미널(또는 VS Code)을 허용한 뒤 그 앱을 완전히 종료하고 다시 실행하세요."
            )
        raise RuntimeError(f"카메라 장치 {index}를 열 수 없습니다.")
    try:
        # 카메라를 켠 직후에는 프레임이 실패하거나 검게 나올 수 있다(맥북 FaceTime 카메라는 첫 프레임까지 약 2.2초).
        # 최대 대기 시간이므로 프레임이 들어오면 바로 진행한다. .env의 REACHY_CAMERA_WARMUP(초)로 조절.
        ok, frame = False, None
        deadline = time.time() + float(os.getenv("REACHY_CAMERA_WARMUP", "5"))
        attempts = 0
        while time.time() < deadline:
            attempts += 1
            ok, frame = camera.read()
            if ok and frame is not None and frame.mean() > 5:
                break
            time.sleep(0.1)
        if not ok or frame is None:
            raise RuntimeError(f"카메라에서 프레임을 읽지 못했습니다 ({attempts}회 시도).")
        ok, image = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("촬영 이미지를 JPEG로 변환하지 못했습니다.")
        return image.tobytes()
    finally:
        camera.release()


def _file_bytes() -> bytes:
    path = os.getenv("REACHY_CAMERA_IMAGE", "").strip()
    if not path:
        raise RuntimeError("REACHY_CAMERA_IMAGE에 이미지 파일 경로를 지정해야 합니다.")
    src = Path(path).expanduser()
    if not src.is_file():
        raise FileNotFoundError(f"지정한 이미지가 없습니다: {src}")
    if src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValueError("JPG, PNG, WEBP 파일만 사용할 수 있습니다.")
    data = src.read_bytes()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("이미지 크기는 최대 10MB입니다.")
    frame = cv2.imdecode(__import__("numpy").frombuffer(data, dtype="uint8"), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("이미지를 읽을 수 없습니다.")
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("이미지 인코딩 실패")
    return encoded.tobytes()


def _bridge_bytes() -> bytes:
    address = os.getenv("REACHY_CAMERA_BRIDGE_URL", "").strip()
    token = os.getenv("REACHY_CAMERA_BRIDGE_TOKEN", "").strip()
    parsed = urlparse(address)
    if parsed.scheme != "http" or not parsed.hostname or not token:
        raise RuntimeError("REACHY_CAMERA_BRIDGE_URL(http)과 TOKEN을 .env에 설정하세요.")
    response = requests.get(
        address.rstrip("/") + "/capture",
        headers={"X-Camera-Token": token},
        timeout=12,
    )
    response.raise_for_status()
    if len(response.content) > 10 * 1024 * 1024 or not response.headers.get("Content-Type", "").startswith("image/jpeg"):
        raise RuntimeError("카메라 브리지에서 올바른 JPEG 응답을 받지 못했습니다.")
    return response.content


def capture_jpeg() -> bytes:
    source = os.getenv("REACHY_CAMERA_SOURCE", "auto").lower().strip()
    if source == "auto":
        # 명시 설정이 있으면 우선하며, 없을 경우 카메라 장치 사용을 시도
        if os.getenv("REACHY_CAMERA_IMAGE"):
            source = "file"
        elif os.getenv("REACHY_CAMERA_BRIDGE_URL"):
            source = "bridge"
        else:
            source = "device"
    methods = {"device": _camera_device_bytes, "file": _file_bytes, "bridge": _bridge_bytes}
    if source not in methods:
        raise ValueError("REACHY_CAMERA_SOURCE는 auto, device, file, bridge 중 하나여야 합니다.")
    try:
        return methods[source]()
    except Exception as exc:
        if source == "device" and platform.system() == "Linux":
            raise RuntimeError(
                "Linux/WSL 카메라 장치를 사용할 수 없습니다. "
                "WSL에서는 REACHY_CAMERA_SOURCE=file 또는 bridge를 설정하세요."
            ) from exc
        raise
