"""팀 공통 LLM 모듈 (Gemini).

- generate_text(): 요약·일기 정리 등 일반 텍스트 생성용
- search_web():    구글 검색으로 최신 정보를 찾아 짧게 요약 (날씨, 뉴스 등)
- ReachyChat:      음성 대화용. 대화 기록을 유지하고 대답+감정을 JSON(ReachyReply)으로 받음.
                   외부 정보가 필요할 때만 search_web 을 자동으로 호출함
- get_reply():     기록 없이 한 번만 묻는 ReachyChat 단축 함수
"""

import os
from collections.abc import Callable
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .prompts import REACHY_SYSTEM, SEARCH_SYSTEM
from .schema import Emotion, ReachyReply

load_dotenv()  # .env 의 GEMINI_API_KEY, GEMINI_MODEL 읽기

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

__all__ = ["Emotion", "ReachyReply",
           "ReachyChat", "generate_text", "search_web", "get_reply"]

_client: genai.Client | None = None
_WEEKDAYS = "월화수목금토일"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(".env 에 GEMINI_API_KEY 가 없습니다.")
        _client = genai.Client(api_key=api_key)
    return _client


def _today() -> str:
    now = datetime.now()
    return f"{now:%Y년 %m월 %d일} {_WEEKDAYS[now.weekday()]}요일"


def generate_text(prompt: str, system: str | None = None, model: str | None = None) -> str:
    # 일반 텍스트 생성. 기사 요약, 일기 정리, 학습 자료 요약 등에 사용.
    response = _get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return response.text


def search_web(query: str, model: str | None = None) -> str:
    # 구글 검색 결과를 3문장 이내로 요약. 검색 도구를 쓰므로 일반 호출보다 느리고 토큰을 더 씀.
    # JSON 강제(response_schema)와 같이 쓰면 검색을 건너뛰는 문제가 있어 별도 호출로 분리했다.
    response = _get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=SEARCH_SYSTEM.format(today=_today()),
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return response.text or "정보 없음"


class ReachyChat:
    # 대화 기록을 유지하는 Reachy 음성 대화 세션.
    #
    # chat = ReachyChat()
    # reply = chat.send("오늘 시험 망쳤어")
    # reply.answer   -> TTS로 읽을 문장
    # reply.emotion  -> Emotion.COMFORTING 등 (모션 모듈 입력)
    #
    # 외부 정보가 필요하면 LLM이 search_query 를 채우고, 그때만 검색 후 한 번 더 물어본다.
    #   일상 대화: LLM 호출 1번 / 검색 필요: 1번 + 검색 1번 + 1번

    def __init__(self, system: str = REACHY_SYSTEM, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.last_search_query: str | None = None  # 직전 send()에서 검색했으면 검색어
        self._chat = _get_client().chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=system.format(today=_today()),
                response_mime_type="application/json",
                response_schema=ReachyReply,
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"      # 추론 수준 Low로 설정(더 빠른 응답을 위해)
            ),
        )

    def _send_raw(self, message: str) -> ReachyReply:
        response = self._chat.send_message(message)
        if isinstance(response.parsed, ReachyReply):
            return response.parsed
        return ReachyReply.model_validate_json(response.text)

    def send(
        self,
        user_text: str,
        on_search: Callable[[ReachyReply], None] | None = None,
    ) -> ReachyReply:
        # on_search: 검색을 시작할 때 호출됨. "잠깐 찾아볼게" 같은 중간 대답을 TTS로 먼저 읽어줄 때 사용.
        self.last_search_query = None
        reply = self._send_raw(user_text)

        query = reply.search_query.strip()
        if not query:
            return reply

        self.last_search_query = query
        if on_search:
            on_search(reply)
        result = search_web(query, model=self.model)
        final = self._send_raw(
            f"[검색 결과: {query}]\n{result}\n\n"
            "위 검색 결과를 바탕으로 사용자에게 대답해. 이번에는 search_query를 빈 문자열로 둬."
        )
        final.search_query = ""
        return final


def get_reply(user_text: str, model: str | None = None) -> ReachyReply:
    # 대화 기록 없이 한 번만 질문할 때.
    return ReachyChat(model=model).send(user_text)
