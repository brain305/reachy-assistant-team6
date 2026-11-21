# 음성 대화: 마이크(STT) → LLM → 대답을 TTS로 읽으면서 감정 모션. (Ctrl+C로 종료)
#
# 터미널 1: reachy-mini-daemon --sim   (시뮬레이터. 꺼져 있으면 모션 없이 음성 대화만)
# 터미널 2: python voice_chat.py

import time
from contextlib import nullcontext

from reachy_mini import ReachyMini

from diary.conversation import DiaryConversation, spoken_text
from motion import EmotionMotion
from stt import SpeechToText
from tts import TextToSpeech


def connect_reachy():
    # media_backend="no_media": 마이크·스피커는 우리 STT/TTS가 쓰므로 SDK가 잡지 않게 함
    try:
        return ReachyMini(media_backend="no_media", timeout=3.0)
    except Exception as e:
        print(f"[motion] Reachy 연결 실패 → 모션 없이 진행 ({type(e).__name__}: {e})")
        return None


print("STT 모델 불러오는 중...")
stt = SpeechToText()
tts = TextToSpeech()
chat = DiaryConversation()  # 대화 기록 유지 (프로그램을 껐다 켜면 초기화)
mini = connect_reachy()


def say(text: str, wait: bool = True, on_start=None) -> None:
    # 음성을 먼저 만든 뒤 on_start(모션 시작)와 재생을 동시에 → 말과 모션의 타이밍을 맞춤
    print(f"Reachy: {text}")
    try:
        speech = tts.synthesize(text)
    except Exception as e:  # 인터넷 끊김 등. 소리가 안 나도 대화와 모션은 계속
        print(f"[tts] 음성 출력 실패: {type(e).__name__}: {e}")
        speech = None
    if on_start:
        on_start()
    if speech is not None:
        tts.play(speech, wait=wait)


with mini if mini else nullcontext():
    motion = EmotionMotion(mini) if mini else None

    def on_search(r) -> None:
        # 검색하는 동안 "잠깐 찾아볼게"를 읽으면서 갸우뚱. 기다리지 않고 바로 검색 시작
        print(f"  (검색: {chat.last_search_query})")
        say(r.answer, wait=False, on_start=lambda: motion and motion.express("curious", 0.5))

    if motion:
        motion.rest()
    print("준비 완료. 말해 보세요. (Ctrl+C로 종료)")

    try:
        while True:
            print("\n듣는 중...")
            audio = stt.record()  # Reachy가 말하는 동안에는 듣지 않음 (say가 끝난 뒤 호출됨)
            if audio is None:
                continue

            # 여기부터가 '말을 끝낸 뒤' 기다리는 시간
            t0 = time.time()
            try:
                text = stt.transcribe(audio)
            except Exception as e:
                print(f"[stt] 인식 실패, 다시 말해 주세요: {type(e).__name__}: {e}")
                continue
            if not text:
                continue
            t1 = time.time()
            print(f"나: {text}")

            try:
                reply = chat.send(text, on_search=on_search)
            except Exception as e:  # 네트워크 오류, API 한도 초과 등
                print(f"[llm] 응답 실패: {type(e).__name__}: {e}")
                continue
            t2 = time.time()

            print(f"  감정={getattr(reply.emotion, 'value', reply.emotion)} 세기={reply.intensity:.1f}")
            print(f"  (STT {t1 - t0:.1f}s + LLM {t2 - t1:.1f}s = 대답까지 {t2 - t0:.1f}s)")
            say(
                spoken_text(reply),
                # 모션은 백그라운드로 시작 → 말과 동시에 움직임
                on_start=lambda: motion and motion.express(reply.emotion, reply.intensity),
            )
            if motion:
                motion.wait()  # 모션이 말보다 길면 끝날 때까지 기다린 뒤 다시 듣기
    except (KeyboardInterrupt, EOFError):
        print("\n종료")
    finally:
        tts.stop()
        chat.close()
