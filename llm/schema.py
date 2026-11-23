from enum import Enum

from pydantic import BaseModel, Field


class Emotion(str, Enum):
    """Reachy가 표현할 수 있는 감정. 모션 모듈이 이 값을 보고 동작을 고른다."""

    HAPPY = "happy"
    SAD = "sad"
    CURIOUS = "curious"
    SURPRISED = "surprised"
    COMFORTING = "comforting"
    NEUTRAL = "neutral"


class Skill(str, Enum):
    """대화 대신 실행할 기능. voice_chat.py가 이 값을 보고 해당 모듈을 부른다."""

    CHAT = "chat"
    NEWS = "news"
    VISION = "vision"
    DIARY = "diary"


class ReachyReply(BaseModel):
    """LLM이 돌려주는 JSON 응답 형식."""

    answer: str = Field(description="사용자에게 TTS로 읽어줄 대답. 반말로 한두 문장.")
    emotion: Emotion = Field(description="대답할 때 Reachy가 표현할 감정")
    intensity: float = Field(
        ge=0.0, le=1.0, description="감정의 세기. 0.0(약하게) ~ 1.0(강하게)"
    )
    search_query: str = Field(
        default="",
        description="오늘 날짜 기준의 외부 정보가 필요할 때만 검색어를 넣는다. 필요 없으면 빈 문자열.",
    )
    skill: Skill = Field(
        default=Skill.CHAT,
        description="대화 대신 실행할 기능. 일반 대화면 chat.",
    )
    skill_query: str = Field(
        default="",
        description="skill이 chat이 아닐 때 기능에 넘길 내용. chat이면 빈 문자열.",
    )
