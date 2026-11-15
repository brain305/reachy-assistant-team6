
import os
import cv2
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def recognize_object(question="내가 손에 들고 있는 게 뭐야?"):
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        raise RuntimeError("카메라를 사용할 수 없습니다.")

    try:
        success, frame = camera.read()
        if not success:
            raise RuntimeError("카메라 촬영 실패")
    finally:
        camera.release()

    # 촬영된 이미지를 JPEG로 변환
    success, image = cv2.imencode(".jpg", frame)
    if not success:
        raise RuntimeError("이미지 변환 실패")

    # Gemini 이미지 인식
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=[
            f"{question} 사진을 보고 한국어로 짧게 대답해. "
            "확실하지 않으면 모른다고 해.",
            types.Part.from_bytes(
                data=image.tobytes(),
                mime_type="image/jpeg"
            )
        ]
    )

    return response.text or "물체를 인식하지 못했어요."
