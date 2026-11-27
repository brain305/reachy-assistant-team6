"""스킬 등록/실행. 비즈니스 로직은 vision/news에 둔다."""

from dataclasses import dataclass
from typing import Callable


@dataclass
class SkillOutcome:
    answer: str
    emotion: str = "neutral"
    intensity: float = 0.5


class SkillRunner:
    def __init__(self, *, recognize=None, summarize=None, send=None):
        # 모듈은 실제 Skill 실행 시에만 불러온다. 예: cv2가 없어도 대화/뉴스 실행 가능.
        # 테스트에서는 의존성 주입으로 카메라/네트워크 사용 없이 검증한다.
        self.recognize = recognize
        self.summarize = summarize
        self.send = send
        self.last_news: tuple[str, str] | None = None
        self._skills: dict[str, Callable[[str], SkillOutcome]] = {
            "vision": self._vision,
            "news": self._news,
            "slack": self._slack,
        }

    def execute(self, skill: str, query: str = "") -> SkillOutcome:
        if skill not in self._skills:
            raise ValueError(f"등록되지 않은 Skill: {skill}")
        return self._skills[skill](query)

    def _vision(self, query: str) -> SkillOutcome:
        if self.recognize is None:
            from vision import recognize_object
            self.recognize = recognize_object
        answer = self.recognize(query or "지금 카메라에 보이는 물체가 뭐야?")
        return SkillOutcome(answer, "curious", 0.7)

    def _news(self, query: str) -> SkillOutcome:
        if self.summarize is None:
            from news import summarize_news
            self.summarize = summarize_news
        summary, links = self.summarize()
        # 성공적으로 요약한 뒤에만 상태 갱신
        self.last_news = (summary, links)
        print("\n[News] 기사 출처:\n" + links)
        return SkillOutcome(summary, "happy", 0.5)

    def _slack(self, query: str) -> SkillOutcome:
        if self.last_news is None:
            return SkillOutcome("아직 요약한 뉴스가 없어요. 먼저 IT 뉴스를 요약해 달라고 해 주세요.")
        # 이 스킬은 사용자가 실제 전송을 요청한 경우에만 라우터에서 선택한다.
        if self.send is None:
            from news.slack_sender import send_to_slack
            self.send = send_to_slack
        self.send(*self.last_news)
        return SkillOutcome("방금 요약한 뉴스와 기사 링크를 슬랙으로 전송했어요.", "happy", 0.6)
