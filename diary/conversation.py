# main의 일반 대화·검색을 재사용하는 연결기. 다른 라우터는 DiaryFeature를 직접 호출한다.
import json

from . import DiaryReply
from .feature import DiaryFeature
from .intent import DiaryAction, INTENT_RULES, LookupItem, exact_intent, validate_intent


def create_chat(model=None):
    from llm import ReachyChat, ReachyReply, DEFAULT_MODEL, _get_client, _today
    from llm.prompts import REACHY_SYSTEM
    from google.genai import types

    class ReplyWithDiary(ReachyReply):
        diary_action: DiaryAction = 'chat'
        diary_entry: str = ''
        diary_history_indices: list[int] = []
        diary_lookup: list[LookupItem] = []
        diary_title: str = ''
        diary_target: str = ''

    system = REACHY_SYSTEM + """
user_text는 사용자 발화, diary_state는 실제 일기 상태다. 일반 대화와 검색은 기존 규칙을 따른다.
일기 규칙의 action/entry/history_indices/lookup/title/target은 각각 diary_ 접두사가 붙은 응답 필드에 넣어라.
clarification은 answer에 넣는다. 일기 작업은 Python이 실행하므로 결과를 추측하지 말고 search_query를 비워라.
검색 결과에는 diary_action=chat으로 답한다.
""" + INTENT_RULES

    class DiaryChat(ReachyChat):
        # main의 send/검색/대화 이력은 상속한다. 확장 응답의 생성·해석만 이 기능 안에서 담당한다.
        def __init__(self):
            self.model = model or DEFAULT_MODEL
            self.last_search_query = None
            self._chat = _get_client().chats.create(model=self.model,
                config=types.GenerateContentConfig(system_instruction=system.format(today=_today()),
                    response_mime_type='application/json', response_schema=ReplyWithDiary))

        def _send_raw(self, message):
            response = self._chat.send_message(message)
            if isinstance(response.parsed, ReplyWithDiary):
                return response.parsed
            return ReplyWithDiary.model_validate_json(response.text)

    return DiaryChat()


class DiaryConversation:
    def __init__(self, chat=None, diary=None):
        self.chat = chat if chat is not None else create_chat()
        self.diary = diary if diary is not None else DiaryFeature()

    @property
    def last_search_query(self):
        return self.chat.last_search_query

    def close(self):
        # 저장하지 않은 이야기를 종료 시 복사할 수 있게 표시한다. 자동 저장은 하지 않는다.
        if self.diary.session.active and self.diary.session.entries:
            print('아직 저장하지 않은 일기 내용이 있습니다. 필요한 원문을 복사해 주세요:')
            print('\n\n'.join(self.diary.session.entries))

    def send(self, text, on_search=None):
        try:
            return self._send(text, on_search)
        finally:
            # 로봇 답변·검색 결과는 저장하지 않는다. 실패한 발화도 사용자가 다시 활용할 수 있다.
            self.diary.remember(text)

    def _send(self, text, on_search=None):
        exact = exact_intent(text)
        if exact is not None:
            return self.diary.apply(text, exact)
        if self.diary.active or self.diary.pending_start:
            reply = self.diary.handle(text)
            if reply is not None:
                return reply
        state = self.diary.state
        reply = self.chat.send(json.dumps({'user_text': text, 'diary_state': state}, ensure_ascii=False),
                               on_search=on_search)
        # 검색에서 받은 외부 정보는 일기 작업을 실행할 권한이 없다.
        if self.chat.last_search_query:
            self.diary.pending_start = False
            return reply
        try:
            intent = validate_intent(getattr(reply, 'diary_action', 'chat'),
                                     getattr(reply, 'diary_entry', ''), text,
                                     getattr(reply, 'diary_history_indices', ()), state['history'],
                                     lookup=getattr(reply, 'diary_lookup', ()), title=getattr(reply, 'diary_title', ''),
                                     target=getattr(reply, 'diary_target', ''), clarification=reply.answer)
        except ValueError:
            self.diary.pending_start = False
            return DiaryReply('일기 요청을 정확히 확인하지 못했어. 기존 내용은 그대로 있으니 다시 말해 줄래?')
        result = self.diary.apply_natural(text, intent)
        return result if result is not None else reply


def spoken_text(reply):
    # 기존 답변 또는 일기 초안을 읽을 문장으로 변환한다. 경로는 읽지 않는다.
    draft = getattr(reply, 'draft', None)
    return reply.answer + '\n\n' + draft if draft and getattr(reply, 'show_draft', False) else reply.answer
