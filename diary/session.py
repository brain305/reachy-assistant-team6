# 사용자별 일기 상태와 공감·작성·저장 흐름.

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .archive import DiaryArchive, DiarySelectionError
from .generation import EMOTIONS, IncompleteResponseError
from .prompts import DIARY_SYSTEM, EMPATHY_SYSTEM
from .storage import DiaryStore, KST
from .intent import makes_operation_claim


@dataclass
class DiaryReply:
    # 뉴스 SkillOutcome과 공통인 answer/emotion/intensity + 일기 전용 부가 정보.
    answer: str
    emotion: str = "neutral"
    intensity: float = 0.4
    draft: str | None = None  # 긴 일기는 대답과 분리해 화면에서 확인한다.
    saved_path: Path | None = None
    draft_source: str | None = None  # model / original
    show_draft: bool = False  # 초안 미리보기를 요청했을 때만 출력한다.


class DiarySession:
    # start → talk(반복) → compose → save. 실패해도 수집한 이야기는 유지한다.

    def __init__(self, generate=None, store=None, max_calls=None):
        if max_calls is not None and max_calls < 1:
            raise ValueError("max_calls는 1 이상이어야 합니다.")
        self.generate = generate
        self.store = store if store is not None else DiaryStore()
        self.archive = DiaryArchive(self._request)
        self.max_calls = max_calls
        self.calls = 0  # 프로그램 실행 중 누적. 새 일기를 시작해도 초기화하지 않는다.
        self.last_error = None
        self.last_api_ok = None
        self._reset()

    def _reset(self):
        # 작성분만 초기화한다. 누적 요청 수와 마지막으로 읽은 파일은 유지한다.
        self.active = False
        self.entries = []
        self.previous_reply = ""
        self.title = ""
        self.draft = None
        self.draft_source = None
        self.saved_path = None
        self.day = None

    @property
    def can_request_empathy(self):
        return self.max_calls is None or self.calls < self.max_calls - 1

    def _request(self, system, payload, *, schema=None):
        if self.max_calls is not None and self.calls >= self.max_calls:
            self.last_error = "이번 실행의 요청 한도에 도달했어"
            raise RuntimeError(self.last_error)
        if self.generate is None:
            from .generation import generate_text
            self.generate = generate_text
        self.calls += 1
        self.last_error = None
        options = {"response_schema": schema} if schema is not None else {}
        try:
            result = self.generate(json.dumps(payload, ensure_ascii=False), system=system, **options)
        except Exception as exc:
            self.last_api_ok = False
            code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            self.last_error = {
                400: "API 키나 요청 설정을 확인해야 해 (400)",
                401: "API 인증에 실패했어 (401)",
                403: "API 접근 권한을 확인해야 해 (403)",
                404: "설정된 모델을 찾지 못했어 (404)",
                429: "LLM 사용량 또는 크레딧 제한에 걸렸어 (429)",
                503: "LLM 서버가 혼잡해 (503)",
                504: "LLM 응답 시간이 초과됐어 (504)",
            }.get(code, "API 연결 또는 실행 중 오류가 발생했어")
            if isinstance(exc, IncompleteResponseError):
                self.last_error = "Gemini 응답이 끝까지 생성되지 않았어"
            raise
        self.last_api_ok = True
        if not isinstance(result, str) or not result.strip():
            self.last_error = "응답 내용이 비어 있어"
            raise ValueError(self.last_error)
        return result.strip()

    def start(self) -> DiaryReply:
        # 새 일기를 시작한다. 작성 중이면 수집한 내용을 덮어쓰지 않는다.
        if self.active:
            return DiaryReply("이미 일기를 쓰고 있어. 계속 이야기하거나 정리, 저장, 취소를 선택해 줘.")
        self._reset()
        self.active = True
        self.day = datetime.now(KST).date()
        return DiaryReply("오늘 어떤 일이 있었어? 편하게 이야기해 줘.", "curious")

    def add_entry(self, text: str) -> DiaryReply | None:
        # 사용자 원문 수집. 명령과 경험이 섞인 입력도 생성 전에 보존한다.
        if not self.active:
            return DiaryReply("먼저 '일기 시작'이라고 말해 줘.")
        text = text.strip()
        if not text:
            return DiaryReply("이야기를 입력해 줘.")
        # 맥락을 조용히 잘라내지 않는다. 한도에 도달하면 먼저 현재 일기를 마무리한다.
        if sum(map(len, self.entries)) + len(text) > 12000:
            return DiaryReply("이야기가 길어졌어. 지금까지의 내용을 먼저 일기로 정리해 줘.")
        self.entries.append(text)
        self.draft = None  # 새 이야기가 생겼다면 이전 초안을 그대로 저장하지 않는다.
        self.draft_source = None
        return None

    def talk(self, text: str, *, empathy: dict | None = None) -> DiaryReply:
        # 원문을 보존하고 공감을 검증한다. 이미 받은 공감이 없을 때만 생성한다.
        error = self.add_entry(text)
        if error:
            return error
        # 마지막 한 번은 일기 정리에 남겨 둔다. 계속 이야기해도 원문은 유지한다.
        if not self.can_request_empathy:
            if self.calls >= self.max_calls:
                return DiaryReply("요청 한도에 도달했어. 이야기는 담아뒀고 원문으로 저장할 수 있어.")
            return DiaryReply("이야기는 담아뒀어. 정리에 쓸 요청을 남겨 두고 공감 요청은 멈췄어. '저장해 줘'로 마무리할 수 있어.")
        try:
            if empathy is None:
                payload = {"entries": self.entries, "previous_reply": self.previous_reply}
                raw = self._request(EMPATHY_SYSTEM, payload)
                if raw.startswith("```") and raw.endswith("```"):
                    raw = "\n".join(raw.splitlines()[1:-1])
                empathy = json.loads(raw)
            else:
                self.calls += 1  # 의도 분류와 함께 받은 공감은 다시 요청하지 않는다.
                self.last_error, self.last_api_ok = None, True
            answer, emotion, strength = empathy["answer"], empathy["emotion"], empathy["intensity"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("공감 답변이 비어 있습니다.")
            if emotion not in EMOTIONS:
                raise ValueError("알 수 없는 감정입니다.")
            if type(strength) not in (int, float) or not 0 <= strength <= 1:
                raise ValueError("감정 강도는 0~1이어야 합니다.")
            if makes_operation_claim(answer):
                self.last_error = "공감 답변에 확인되지 않은 실행 정보가 포함됐어"
                return DiaryReply("이야기는 담아뒀어. 일기를 저장하거나 읽고 싶으면 따로 말해 줘.")
            reply = DiaryReply(answer.strip(), emotion, strength)
            self.previous_reply = reply.answer
            return reply
        except Exception:
            # 원시 API 예외는 출력하지 않는다. 키·요청 정보가 로그에 섞이지 않도록 한다.
            if self.last_api_ok:
                self.last_error = "공감 응답의 형식이 올바르지 않아"
            return DiaryReply(f"이야기는 담아뒀어. {self.last_error or '공감 답변을 만들지 못했어'}. 저장·조회 명령은 계속 사용할 수 있어.")

    def compose(self, title: str = '') -> DiaryReply:
        # 현재 발언으로 초안만 만든다. 실제 파일 저장은 별도의 명시적 요청이다.
        if not self.active or not self.entries:
            return DiaryReply("일기를 시작하고 오늘 있었던 일을 먼저 이야기해 줘.")
        # 실패해 준비한 원문은 정리를 다시 요청했을 때만 재시도한다. 저장 요청은 원문을 그대로 보존한다.
        if self.draft_source != "model":
            try:
                self.draft = self._request(DIARY_SYSTEM, {"date": self.day.isoformat(), "entries": self.entries})
                self.draft_source = "model"
            except Exception:
                self._original_draft()
        self._apply_title(title)
        if self.draft_source == "original":
            reason = self.last_error or "이번 실행의 요청 한도에 도달했어"
            retry = " 다시 정리해 달라고 말하면 재시도할 수 있어." if self.max_calls is None or self.calls < self.max_calls else ""
            return DiaryReply(f"{reason}. AI가 정리한 일기 대신 네가 말한 원문을 준비했어.{retry}",
                              draft=self.draft, draft_source="original", show_draft=True)
        return DiaryReply("저장 전 초안이야.", draft=self.draft, draft_source="model", show_draft=True)

    def _original_draft(self):
        self.draft = "[원문 기록 — AI 정리 없음]\n\n" + "\n\n".join(self.entries)
        self.draft_source = "original"

    def _apply_title(self, title):
        # 제목만 바꿀 때는 저장할 본문을 다시 생성하지 않는다.
        self.title = title or self.title
        if self.title:
            first, _, body = self.draft.partition('\n')
            if self.draft_source == "original":
                body = "[원문 기록 — AI 정리 없음]\n\n" + "\n\n".join(self.entries)
            self.draft = self.title + "\n\n" + (body.strip() or first)

    def request_save(self, original: bool = False, *, title: str = '') -> DiaryReply:
        # 명시적인 저장 요청. 초안이 없으면 생성한 뒤 파일까지 저장한다.
        if self.saved_path is not None:
            return self.save()
        if not self.active or not self.entries:
            return DiaryReply("일기를 시작하고 저장할 이야기를 먼저 들려줘.")
        if original:
            self._original_draft()
        if self.draft is None:
            self.compose(title)
        else:
            self._apply_title(title)
        return self.save()

    def save(self) -> DiaryReply:
        # 준비된 초안을 저장한다. 실패 시 세션 유지, 성공 시 작성 종료, 재호출은 중복 방지.
        if self.saved_path is not None:
            return DiaryReply("이미 저장한 일기야.", saved_path=self.saved_path)
        if not self.active or self.draft is None:
            return DiaryReply("먼저 '일기로 정리해 줘'라고 말해서 초안을 만들어 줘.")
        try:
            self.saved_path = self.store.save(self.day, self.draft)
        except OSError:
            return DiaryReply("파일을 저장하지 못했어. 초안은 유지했으니 저장 위치와 권한을 확인해 줘.", draft=self.draft, draft_source=self.draft_source)
        self.archive.focus = self.saved_path
        self.archive.choices.clear()
        self.active = False
        answer = "일기를 저장했어. 오늘 이야기를 들려줘서 고마워."
        if self.draft_source == "original":
            answer = "AI가 정리한 일기 대신 네가 말한 원문을 파일로 저장했어."
        return DiaryReply(answer, "happy", draft=self.draft, saved_path=self.saved_path, draft_source=self.draft_source)

    def cancel(self) -> DiaryReply:
        # 이번 메모리 작성분만 취소한다. 기존 일기 파일은 삭제하지 않는다.
        self._reset()
        return DiaryReply("이번 일기 작성을 종료했어. 이미 저장된 일기는 그대로 있어.")

    def read_latest(self) -> DiaryReply:
        return self.read_saved(('latest',))

    def read_saved(self, items, target='') -> DiaryReply:
        # 한 요청에서 개수와 본문이 같은 파일 목록을 기준으로 답하도록 한다.
        parts = []
        try:
            files = self.store.files()
            # 주제까지 지목하면 '최근 것 중 사고 이야기'의 본문은 주제에 맞는 한 편이다.
            reads = items
            if target:
                reads = [i for i in items if i.startswith('count_')] + ['selected']
            for item in reads:
                if item == 'count_today':
                    prefix = datetime.now(KST).date().isoformat() + '_'
                    count = sum(path.name.startswith(prefix) for path in files)
                    parts.append(f'오늘 날짜로 저장된 일기는 {count}개야.')
                elif item == 'count_all':
                    parts.append(f'저장된 일기는 총 {len(files)}개야.')
                elif files:
                    path = self.archive.select(target if item == 'selected' else item, files)
                    parts.append(path.read_text(encoding='utf-8'))
                    self.archive.focus = path
                    self.archive.choices.clear()
                elif not parts:
                    parts.append('아직 저장한 일기가 없어.')
        except DiarySelectionError as error:
            parts.append(str(error))
            return DiaryReply('\n\n'.join(parts), 'curious')
        except Exception:
            parts.append('저장된 일기를 읽지 못했어. 파일 상태를 확인해 줘.')
            return DiaryReply('\n\n'.join(parts))
        if not files and self.draft and any(item in ('oldest', 'latest') for item in items):
            parts.append("현재 초안은 아직 저장 전이야. '저장해 줘'로 저장할 수 있어.")
            return DiaryReply('\n\n'.join(parts), draft=self.draft, draft_source=self.draft_source)
        return DiaryReply('\n\n'.join(parts))

    def change_saved(self, action, target, query) -> DiaryReply:
        if not query.strip():
            return DiaryReply("일기에 추가하거나 고칠 내용을 알려 줘.", "curious")
        try:
            path = self.archive.select(target or "current", self.store.files())
            original = path.read_text(encoding="utf-8")
            revised = self.archive.revise(original, action, query)
            if revised != original and not self.store.update(path, original, revised):
                return DiaryReply("다른 곳에서 일기가 바뀌었어. 다시 읽고 수정해 줘.")
        except DiarySelectionError as error:
            return DiaryReply(str(error), "curious")
        except Exception:
            return DiaryReply("일기 수정을 완료하지 못했어. 다시 요청해 줘.")
        self.archive.focus = path
        self.archive.choices.clear()
        if self.saved_path == path:
            self.draft = revised.partition('\n')[2].strip()
        answer = "이미 반영된 내용이야." if revised == original else "그 일기에 내용을 반영했어."
        return DiaryReply(answer, saved_path=path)

    def status(self) -> DiaryReply:
        # 현재 세션의 작성·저장 상태만 확인한다.
        if self.saved_path is not None:
            return DiaryReply("현재 일기는 파일로 저장됐어.", saved_path=self.saved_path)
        if not self.active:
            return DiaryReply("지금은 일기를 작성하고 있지 않아. '일기 시작'으로 시작할 수 있어.")
        return DiaryReply(f"일기 작성 중이야. 이야기 {len(self.entries)}개를 메모리에 담았고, 아직 파일로 저장하지 않았어. '저장해 줘'로 저장할 수 있어.")
