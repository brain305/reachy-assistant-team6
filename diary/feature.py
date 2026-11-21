# 외부 실행기에서 가져다 쓸 수 있는 일기 기능. 공통 라우터를 소유하지 않는다.

from datetime import datetime

from .session import DiaryReply, DiarySession
from .storage import KST
from .intent import COMMANDS, DiaryIntent, DiaryIntentRouter, is_simple_assent, validate_intent


class DiaryFeature:
    # 대화마다 하나씩 생성한다. 외부 라우터는 execute, 자연어 입력은 handle을 사용한다.
    def __init__(self, session=None, router=None):
        from .generation import generate_text
        self.session = session if session is not None else DiarySession()
        self.router = router if router is not None else DiaryIntentRouter(generate_text)
        self.paused = False
        self.pending_start = False
        self.history = []
        self.history_day = datetime.now(KST).date()
        self.history_truncated = False

    @property
    def active(self):
        # 현재 일기 이야기를 받고 있는지. 잠시 중단한 일기는 False다.
        return self.session.active and not self.paused

    def remember(self, text):
        # 공통 실행기가 매 발화 처리 후 원문만 전달한다. 이 단계에서는 API·파일을 사용하지 않는다.
        self._refresh_history()
        text = text.strip()
        if len(text) > 12000:
            self.history_truncated = True
            return
        if text:
            self.history.append(text)
        while sum(map(len, self.history)) > 12000:
            self.history.pop(0)
            self.history_truncated = True

    def _refresh_history(self):
        today = datetime.now(KST).date()
        if self.history_day != today:
            self.history.clear()
            self.history_day, self.history_truncated = today, False

    @property
    def state(self):
        # 공통 대화와 일기 분류기에 같은 실제 상태를 제공한다.
        self._refresh_history()
        return dict(active=self.active, paused=self.paused, has_entries=bool(self.session.entries),
                    has_saved=self.session.saved_path is not None, has_draft=self.session.draft is not None,
                    pending_start=self.pending_start, has_selected_diary=self.session.archive.focus is not None,
                    candidate_count=len(self.session.archive.choices), history=list(self.history))

    def execute(self, action: str, query: str = '', *, lookup=(), target='') -> DiaryReply:
        # 이미 의도가 정해진 요청은 Gemini 분류를 건너뛴다.
        if action not in COMMANDS:
            raise ValueError(f'지원하지 않는 일기 동작: {action}')
        if action == 'talk' and not self.active:
            return DiaryReply('일기 작성을 시작하거나 중단한 일기를 이어 쓰겠다고 말해 줘.')
        intent = validate_intent(action, query if action in ('start', 'append') else '', query, lookup=lookup, target=target)
        return self.apply(query, intent)

    def handle(self, text: str) -> DiaryReply | None:
        # 선택적 자연어 처리. 일반 대화/분류 실패는 None이므로 호출자가 처리한다.
        if not text.strip():
            return DiaryReply('잘 듣지 못했어. 다시 말해 줄래?')
        if len(text) > 12000:
            return DiaryReply('한 번에 듣기에는 이야기가 길어. 나눠서 들려줄래?')
        # 작성 중에는 의도와 공감을 함께 받되, 마지막 요청은 기존처럼 일기 정리에 남겨 둔다.
        combined = self.active and self.session.can_request_empathy
        context = dict(entries=self.session.entries, previous_reply=self.session.previous_reply) if combined else {}
        try:
            intent = self.router.choose(text, with_empathy=combined, **context, **self.state)
        except Exception:
            # 일반 대화/검색을 막지 않는다. 호출자가 공통 대화 경로에서 다시 판단한다.
            return None
        return self.apply_natural(text, intent)

    def apply_natural(self, text, intent):
        if intent.action in ('compose', 'save') and text.rstrip(' .?!…').endswith(('제목은', '제목을')):
            return DiaryReply('어떤 제목으로 남길까?', 'curious')
        if is_simple_assent(text) and intent.action != 'chat':
            intent = DiaryIntent('start' if self.pending_start else 'clarify')
        return self.apply(text, intent)

    def apply(self, text, intent):
        # 자연어 해석 결과를 적용한다. 외부의 명시적 호출은 execute를 사용한다.
        action = intent.action
        self.pending_start = False
        if action == 'chat':
            return None
        if action in ('append', 'edit'):
            return self.session.change_saved(action, intent.target, intent.entry if action == 'append' else text)
        if action == 'confirm_start':
            if self.session.active:
                return self.session.status()
            self.pending_start = True
            return DiaryReply('지금 새 일기를 함께 작성할까?', 'curious')
        if action == 'clarify':
            return DiaryReply(intent.clarification.strip() or '일기로 하고 싶은 일을 조금 더 말해 줄래?', 'curious')
        if action in ('pause', 'resume'):
            if not self.session.active:
                return DiaryReply('지금 작성 중인 일기는 없어. 편하게 이야기해 줘.')
            self.paused = action == 'pause'
            if self.paused:
                return DiaryReply('일기는 잠시 멈출게. 지금 내용은 저장하지 않고 유지할게.')
            return self.session.status()
        if action == 'talk':
            return self.session.talk(text, empathy=intent.empathy) if self.active else None
        if action == 'read':
            return self.session.read_saved(intent.lookup or ('latest',), intent.target)
        if action == 'status':
            return self.session.status()
        if action == 'cancel':
            if not self.session.active:
                return DiaryReply('지금은 취소할 작성분이 없어.')
            self.history.clear()
            self.paused = False
            self.history_truncated = False
            return self.session.cancel()
        if action == 'start':
            self.paused = False
            started = self.session.start()
            return self.session.talk(intent.entry) if intent.entry else started
        if action in ('compose', 'save', 'raw'):
            return self._finish_diary(text, intent)
        return DiaryReply('일기 요청을 이해하지 못했어. 다시 말해 줄래?')

    def _finish_diary(self, text, intent):
        # 가져올 원문 전체를 확인한 뒤 한 번에 반영한다. 한도 초과 시 기존 초안이 유지된다.
        action = intent.action
        if intent.history_indices:
            history = self.state['history']
            validate_intent(action, intent.entry, text, intent.history_indices, history)
            existing = self.session.entries if self.session.active else []
            selected = list(dict.fromkeys([history[i] for i in intent.history_indices] + existing))
            if sum(map(len, selected)) + len(intent.entry) > 12000:
                return DiaryReply('일기로 정리할 이야기가 길어. 범위를 나눠서 요청해 줘.')
            if selected != existing:
                if not self.session.active:
                    self.session.start()
                self.session.entries = selected
                self.session.draft = self.session.draft_source = None
        if intent.entry:
            if not self.session.active:
                self.session.start()
            error = self.session.add_entry(intent.entry)
            if error:
                return error
        if action == 'compose':
            reply = self.session.compose(intent.title)
        else:
            reply = self.session.request_save(original=action == 'raw', title=intent.title)
        if not self.session.active:
            self.paused = False
        if intent.history_indices and self.history_truncated:
            reply.answer = '대화가 길어 최근에 보관한 이야기 범위로 정리했어. ' + reply.answer
        return reply
