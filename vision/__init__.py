"""이미지 인식 Skill의 핵심 기능."""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .camera import capture_jpeg

load_dotenv()


def recognize_object(question: str = "내가 손에 들고 있는 게 뭐야?") -> str:
    image_data = capture_jpeg()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(".env의 GEMINI_API_KEY를 설정하세요.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=[
            f"{question} 사진을 보고 한국어로 간결하게 답해 줘. 확실하지 않으면 모른다고 해.",
            types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
        ],
    )
    return response.text or "물체를 인식하지 못했어요."
