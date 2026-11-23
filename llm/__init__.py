"""팀 공통 LLM 모듈 (Gemini).

- generate_text(): 요약·일기 정리 등 일반 텍스트 생성용 (images= 로 JPEG 이미지 함께 전송 가능)
- generate_json(): 정해진 형식(pydantic 모델)의 JSON으로 답을 받을 때
- search_web():    구글 검색으로 최신 정보를 찾아 짧게 요약 (날씨, 뉴스 등)
- ReachyChat:      음성 대화용. 대화 기록을 유지하고 대답+감정을 JSON(ReachyReply)으로 받음.
                   외부 정보가 필요할 때만 search_web 을 자동으로 호출함
- get_reply():     기록 없이 한 번만 묻는 ReachyChat 단축 함수
- today():         프롬프트에 넣을 오늘 날짜 문자열 ("2026년 11월 23일 월요일")
"""

import os
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from .prompts import REACHY_SYSTEM, SEARCH_SYSTEM
from .schema import Emotion, ReachyReply, Skill

load_dotenv()  # .env 의 GEMINI_API_KEY, GEMINI_MODEL 읽기

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
TIMEOUT_MS = 30_000  # 모든 Gemini 요청의 제한 시간. 네트워크가 끊겨도 대화가 멈추지 않게

__all__ = ["Emotion", "ReachyReply", "Skill",
           "ReachyChat", "generate_text", "generate_json", "search_web", "get_reply", "today"]

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None
_WEEKDAYS = "월화수목금토일"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(".env 에 GEMINI_API_KEY 가 없습니다.")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client


def today() -> str:
    now = datetime.now()
    return f"{now:%Y년 %m월 %d일} {_WEEKDAYS[now.weekday()]}요일"


def _contents(prompt: str, images: list[bytes] | None) -> str | list:
    # 이미지가 있으면 [이미지..., 프롬프트] 순서로 묶는다. 이미지는 JPEG 바이트만 받는다.
    if not images:
        return prompt
    parts = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images]
    return [*parts, prompt]


def generate_text(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    images: list[bytes] | None = None,
) -> str:
    # 일반 텍스트 생성. 기사 요약, 일기 정리, 학습 자료 요약 등에 사용.
    response = _get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=_contents(prompt, images),
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return response.text


def generate_json(
    prompt: str,
    schema: type[T],
    system: str | None = None,
    model: str | None = None,
    images: list[bytes] | None = None,
) -> T:
    # schema(pydantic 모델) 형식의 JSON으로 답을 받아 그 객체로 돌려준다.
    # 의도 분류, 일기 생성, 이미지 설명처럼 정해진 칸이 필요한 결과에 사용.
    response = _get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=_contents(prompt, images),
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    if isinstance(response.parsed, schema):
        return response.parsed
    return schema.model_validate_json(response.text)


def search_web(query: str, model: str | None = None) -> str:
    # 구글 검색 결과를 3문장 이내로 요약. 검색 도구를 쓰므로 일반 호출보다 느리고 토큰을 더 씀.
    # JSON 강제(response_schema)와 같이 쓰면 검색을 건너뛰는 문제가 있어 별도 호출로 분리했다.
    response = _get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=SEARCH_SYSTEM.format(today=today()),
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
    #
    # 다른 기능이 필요하면 LLM이 skill 을 채운다. 이때는 검색하지 않고 바로 돌려주며,
    # 실제 기능 실행은 호출한 쪽(voice_chat.py)이 reply.skill 을 보고 한다.
    # 기능 결과를 대화에 남기려면 chat.remember(결과) → 다음 send() 때 같이 보내진다 (추가 호출 없음).

    def __init__(self, system: str = REACHY_SYSTEM, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.last_search_query: str | None = None  # 직전 send()에서 검색했으면 검색어
        self._notes: list[str] = []  # remember()로 쌓아 둔 기능 결과. 다음 send()에 붙여 보냄
        self._chat = _get_client().chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=system.format(today=today()),
                response_mime_type="application/json",
                response_schema=ReachyReply,
            ),
        )

    def _send_raw(self, message: str) -> ReachyReply:
        response = self._chat.send_message(message)
        if isinstance(response.parsed, ReachyReply):
            return response.parsed
        return ReachyReply.model_validate_json(response.text)

    def remember(self, text: str) -> None:
        # 기능 실행 결과(뉴스 요약 등)를 저장해 둔다. 다음 send() 때 사용자 말 앞에 붙여 보낸다.
        self._notes.append(text)

    def send(
        self,
        user_text: str,
        on_search: Callable[[ReachyReply], None] | None = None,
    ) -> ReachyReply:
        # on_search: 검색을 시작할 때 호출됨. "잠깐 찾아볼게" 같은 중간 대답을 TTS로 먼저 읽어줄 때 사용.
        self.last_search_query = None
        message = user_text
        if self._notes:
            notes = "\n\n".join(self._notes)
            message = f"[직전 기능 결과]\n{notes}\n\n[사용자]\n{user_text}"
        reply = self._send_raw(message)
        self._notes.clear()  # 전송에 성공했을 때만 비움. 실패하면 다음 send()에 다시 붙는다

        if reply.skill != Skill.CHAT:
            reply.search_query = ""  # 기능 우선. 검색하지 않는다
            return reply

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
        final.skill, final.skill_query = Skill.CHAT, ""  # 검색 결과로 대답하는 단계라 기능 분기 없음
        return final


def get_reply(user_text: str, model: str | None = None) -> ReachyReply:
    # 대화 기록 없이 한 번만 질문할 때.
    return ReachyChat(model=model).send(user_text)
