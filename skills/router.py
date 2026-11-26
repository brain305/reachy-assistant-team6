"""Gemini의 구조화 출력으로 사용자 의도에 맞는 Skill을 선택한다.

주의: 단어 검색/조건문으로 결정하지 않는다. 
호출 전 승인이 필요한 Skill은
실행 모듈에서 확인하도록 분리하였다.
"""

import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


class SkillChoice(BaseModel):
    skill: Literal["chat", "vision", "news", "slack"] = Field(
        description="요청을 실행할 스킬. 일반 대화와 사용법 질문은 chat"
    )
    query: str = Field(
        default="", description="vision 분석 질문 등 스킬에 넘길 원래 의미의 요청"
    )


SYSTEM = """너는 Reachy Mini 개인 비서의 Skill 선택기야.
사용자의 의도를 문맥으로 판단해 정확히 하나의 스킬을 선택해. 실제 스킬은 Python이 실행한다.
- chat: 일반 대화, 정보성 질문, 사용법 설명. 카메라/뉴스/슬랙이라는 단어가 있더라도 단순 설명이나 질문이면 chat.
- vision: 지금 주변이나 손에 든 물건을 실제 카메라로 촬영해 인식해 달라는 명시적 요청.
- news: 실제 IT 영어 뉴스 기사를 새로 수집하고 요약해서 읽어달라는 요청.
- slack: 앞서 생성한 뉴스 요약을 Slack 채널에 실제로 전송해 달라는 명시적 요청.
단순히 '슬랙으로 보내는 방법은?'은 chat, '카메라에 대해 알려줘'도 chat.
확실하지 않으면 chat으로 판단해. 실제로 보낼 뉴스 요약이 있는지 정보도 고려해.
어떤 스킬도 호출하지 않고 평범한 대답을 만드는 경우에는 chat을 선택해.
"""


class SkillRouter:
    def __init__(self, client=None, model: str | None = None):
        self.client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    def choose(self, user_text: str, *, has_news: bool = False) -> SkillChoice:
        response = self.client.models.generate_content(
            model=self.model,
            contents=(
                f"최근에 저장된 뉴스 요약 있음: {'예' if has_news else '아니요'}\n"
                f"사용자 메시지: {user_text}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_schema=SkillChoice,
                temperature=0,
            ),
        )
        if isinstance(response.parsed, SkillChoice):
            return response.parsed
        if not response.text:
            raise RuntimeError("Skill 라우터의 응답이 비어 있습니다.")
        return SkillChoice.model_validate_json(response.text)
