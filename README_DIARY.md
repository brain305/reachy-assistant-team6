# Reachy의 감정 공감과 일기

기존 팀 가상환경에서 프로젝트 루트의 `python voice_chat.py`를 실행한다. Gemini 설정은 프로젝트의 `.env`에서 `GEMINI_API_KEY`와 선택 항목인 `GEMINI_MODEL`을 읽는다.

개발용 `tests/text_chat.py`가 있는 로컬 작업본에서는 같은 위치에서 `python -m tests.text_chat`을 실행해 키보드로 시험할 수 있다. 음성 실행과 같은 Gemini API와 저장 폴더를 사용하며 `/exit`로 종료한다. 두 프로그램을 별도로 실행하면 미저장 대화 이력은 각각의 프로세스에만 있다. PR의 음성 실행에는 `tests/`가 필요하지 않다.

| 사용자가 하는 말 | Reachy의 동작 |
|---|---|
| “일기 쓰는 법 알려줘” | 일반 대화로 답한다. |
| “일기 시작” → “발표 준비 때문에 힘들었어” | 사용자 원문을 모으고 공감 답변과 모션용 감정·강도를 만든다. |
| 일반 대화 후 “앞에서 이야기한 오늘 일을 일기로 정리해 줘” | 앞서 말한 경험을 골라 일기를 작성·저장하고 완료 안내만 읽는다. |
| “저장하지 말고 초안만 보여줘” | 초안을 미리 보여 준다. |
| 두 번째 이야기를 한 뒤 “이것도 일기로 만들어 줘. 제목은…” | 제목을 이어 말할 때까지 기다린다. “제목은 연결 테스트의 하루로 해줘”처럼 답하면 새 이야기에 그 제목을 붙여 저장한다. |
| “최근 일기 읽어줘” | 가장 최근 일기 파일의 실제 내용을 읽는다. |
| “최근 것 중 운이 안 좋았던 날에 대한 일기 읽어줘” | 제목과 사건 단서로 저장된 일기를 찾아 읽는다. 여러 편이 맞으면 날짜·제목과 후보 번호를 알려 준다. |
| “그 일기에 점심으로 연어를 먹었다는 것도 추가해 줘” | 방금 저장하거나 읽은 파일의 끝에 내용을 덧붙인다. 수정 완료만 알려 준다. |
| “가장 최근 일기에서 방어를 광어로 고쳐줘” | 선택한 파일에서 해당 부분만 고친다. 추가·수정 후 파일명과 일기 수는 유지된다. |
| “오늘 자 일기 몇 개 있어?” | 한국 날짜 기준으로 오늘 날짜의 저장 파일 수를 답한다. |
| “일기가 총 몇 개 있고, 가장 오래된 일기를 읽어줘” | 전체 개수를 말한 뒤 첫 일기 파일의 본문을 읽는다. 개수만 물으면 본문을 읽지 않는다. |

일기는 기본적으로 프로젝트의 `data/diary/YYYY-MM-DD_시각_고유값.md`에 UTF-8로 저장된다. 작성 중 이야기와 미저장 초안은 메모리에 있으며 프로그램을 종료하면 사라진다. Gemini 정리에 실패한 상태에서 저장을 요청하면 사용자 원문임을 파일과 응답에 표시한다. 파일 쓰기가 실패하면 초안을 유지하고 실패를 알린다.

오늘 개수는 작성 시작 시점의 한국 날짜로 센다. 첫 일기와 최근 일기는 파일명에 기록된 일기 날짜·시각 순서로 정한다. 정확한 제목은 로컬에서 찾고, 주제로 찾을 때는 Gemini에 저장된 일기의 제목과 본문 발췌를 보내 대조한다. 정정할 때는 선택한 일기의 내용을 보내 교체할 구절을 구한다. 대상이 여러 편이면 “2번 일기 읽어줘”처럼 번호와 원하는 작업을 말할 수 있다. 새로 실행했을 때는 제목·사건 또는 “최근 일기”로 대상을 지정한다. 임의 날짜별 조회와 일기 파일 삭제는 지원 범위 밖이다.

## voice_chat.py에 연결한 방법

1. 기존 음성 루프를 시작할 때 `DiaryConversation()`을 **한 번** 생성한다. 매 발화마다 같은 인스턴스에 전사된 문자열을 `chat.send(text, on_search=on_search)`로 보낸다.
2. 연결기는 기존 `ReachyChat.send()`의 일반 대화 이력과 검색 콜백을 사용한다. 일기 동작은 내부의 `DiaryFeature`에 전달한다. 일기 작성 중 경험을 이야기하면 보통 Gemini 한 번으로 의도와 공감 답변을 함께 받는다.
3. 음성 루프는 `spoken_text(reply)`를 TTS에 전달하고 재생 시작 시 `motion.express(reply.emotion, reply.intensity)`를 호출한다. 일반 응답의 감정 열거형과 일기 응답의 문자열을 모두 표시한다. 저장 시에는 완료 안내를, 읽기 요청 시에는 본문을 읽는다.
4. Ctrl+C 또는 입력 종료 시 TTS를 정지하고 `chat.close()`를 호출한다. 작성 중인 원문이 있으면 종료 전에 콘솔에서 복사할 수 있다.

현재 main의 대화 생성·응답 해석에 의존하는 부분은 `diary/conversation.py`의 `create_chat()`에 모여 있다. 공통 라우터가 생기면 아래처럼 일기 기능만 직접 연결할 수 있다.

## 다른 기능에서 가져다 쓰기

```python
from diary import DiaryFeature
from diary.conversation import spoken_text

# 사용자 대화마다 한 번 생성하고, 발화 사이에 인스턴스를 유지한다.
diary = DiaryFeature()
diary.execute("start")
empathy = diary.execute("talk", "오늘 발표를 마쳐서 뿌듯했어.")
print(empathy.answer, empathy.emotion, empathy.intensity)

saved = diary.execute("save")  # 초안이 없으면 여기서 정리하고 저장한다.
print(spoken_text(saved))       # 사용자에게 전달할 저장 결과
if saved.saved_path:
    print(saved.saved_path)     # 파일 작업이 필요한 호출자용 경로
print(diary.execute("read").answer)
print(diary.execute("read", lookup=("count_all", "oldest")).answer)
print(diary.execute("read", target="발표 준비로 힘들었던 날").answer)
print(diary.execute("append", "발표 후에는 마음이 편해졌다.", target="latest").answer)
```

| 인터페이스 | 호출자의 사용 방법 |
|---|---|
| `execute(action, query='', *, lookup=(), target='')` | 라우터가 동작을 정했을 때 호출한다. 의도 분류를 생략하며 `DiaryReply`를 반환한다. `target`은 제목·주제, `latest`, `oldest`, `current` 또는 후보 번호(`#2`)다. |
| `handle(text)` | 일기 모듈에 자연어 해석까지 맡긴다. 반환값이 `None`이면 일반 대화나 다른 기능으로 넘긴다. |
| `remember(text)` | 자체 라우터를 쓸 때 **각 발화 처리 후** 사용자 원문을 한 번 전달한다. 일반 대화 내용도 나중에 일기로 정리할 수 있다. `DiaryConversation.send()`를 쓰면 자동 처리된다. |
| `active`, `state` | 현재 이야기를 수집하는지와 작성·중단·저장 상태를 확인한다. `state`에는 사용자 발화 이력도 들어 있다. |

`execute`가 지원하는 동작은 다음과 같다.

| 동작 | 결과 |
|---|---|
| `start`, `talk` | 작성 시작, 사용자 이야기 추가·공감. `start`의 선택적 `query`는 첫 이야기로 사용한다. |
| `compose`, `save`, `raw` | 각각 초안 미리보기, 정리한 일기 저장, 사용자 원문 그대로 저장. |
| `read` | 기본은 최근 본문. `lookup`에 오늘 개수(`count_today`), 전체 개수(`count_all`), 첫 본문(`oldest`), 최근 본문(`latest`)을 요청 순서로 지정할 수 있다. |
| `status` | 현재 작성·저장 상태 조회. |
| `append`, `edit` | `query`에 각각 덧붙일 문장, 구체적인 수정 요청을 전달한다. 대상 생략 시 마지막으로 읽거나 저장한 일기가 필요하다. |
| `pause`, `resume`, `cancel` | 작성분을 유지하며 중단·재개하거나 현재 미저장 작성분을 취소한다. |

### 반환 필드

| `DiaryReply` 필드 | 의미 |
|---|---|
| `answer: str` | 사용자에게 말할 결과. `read`는 요청한 개수, 본문 또는 둘을 함께 반환한다. |
| `emotion: str`, `intensity: float` | Reachy가 표현할 감정과 모션 강도(0~1). 감정 값은 happy, sad, curious, surprised, comforting, neutral 중 하나. |
| `draft: str \| None`, `show_draft: bool` | 생성한 텍스트와 미리보기 표시 여부. TTS 문장은 `spoken_text(reply)`로 얻는다. |
| `saved_path: Path \| None` | 저장·수정한 경로. 중복 저장 안내와 저장 상태 확인에도 포함된다. |
| `draft_source: str \| None` | `model`이면 Gemini가 정리한 글, `original`이면 원문 기록. |

### 저장 위치와 대화 이력

저장 폴더를 직접 지정하려면 `from diary import DiarySession, DiaryStore`로 가져와 `DiaryFeature(session=DiarySession(store=DiaryStore("data/my-diaries")))`로 생성한다. 여러 사용자의 파일을 분리하려면 사용자별 저장 폴더도 각각 지정한다.

일기에 참조하는 일반 대화 원문은 한국 날짜 기준 현재 실행에서 최근 12,000자까지 메모리에 보관한다. 과거 발화를 일기로 만들어 달라는 요청에서는 Gemini가 고른 번호를 검사한 뒤 해당 사용자 원문을 일기 자료로 사용한다. 날짜가 바뀌거나 작성 중인 일기를 취소하면 이 임시 이력을 비운다.
