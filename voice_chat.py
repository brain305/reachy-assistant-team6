"""Reachy Mini: STT → LLM Skill 라우팅 → 실행 결과 TTS/감정 모션.

터미널 1: reachy-mini-daemon --sim
터미널 2: python voice_chat.py
"""

import time
from contextlib import nullcontext

from reachy_mini import ReachyMini
from llm import ReachyChat
from motion import EmotionMotion
from skills.router import SkillRouter
from skills.runner import SkillRunner
from stt import SpeechToText
from tts import TextToSpeech


def connect_reachy():
    try:
        return ReachyMini(media_backend="no_media", timeout=3.0)
    except Exception as exc:
        print(f"[motion] Reachy 연결 실패 → 모션 없이 진행: {exc}")
        return None


def main():
    print("STT 모델 불러오는 중...")
    stt = SpeechToText()
    tts = TextToSpeech()
    chat = ReachyChat()
    router = SkillRouter()
    runner = SkillRunner()
    mini = connect_reachy()

    def say(text: str, wait: bool = True, on_start=None):
        print(f"Reachy: {text}")
        try:
            speech = tts.synthesize(text)
        except Exception as exc:
            print(f"[tts] 음성 생성 실패: {type(exc).__name__}: {exc}")
            speech = None
        if on_start:
            on_start()
        if speech is not None:
            tts.play(speech, wait=wait)

    with mini if mini else nullcontext():
        motion = EmotionMotion(mini) if mini else None

        def on_search(reply):
            print(f"  (검색: {chat.last_search_query})")
            say(reply.answer, wait=False,
                on_start=lambda: motion and motion.express("curious", 0.5))

        if motion:
            motion.rest()
        print("준비 완료. 말해 보세요. (Ctrl+C로 종료)")

        try:
            while True:
                print("\n듣는 중...")
                audio = stt.record()
                if audio is None:
                    continue
                t0 = time.time()
                try:
                    text = stt.transcribe(audio)
                except Exception as exc:
                    print(f"[stt] 인식 실패: {type(exc).__name__}: {exc}")
                    continue
                if not text:
                    continue
                print(f"나: {text}")

                try:
                    choice = router.choose(text, has_news=runner.last_news is not None)
                    print(f"[Skill Router] {choice.skill} (선택 {time.time() - t0:.1f}s)")
                except Exception as exc:
                    print(f"[Router] 판단 실패 → 일반 대화: {type(exc).__name__}: {exc}")
                    choice = None

                if choice and choice.skill != "chat":
                    try:
                        result = runner.execute(choice.skill, choice.query or text)
                        say(result.answer,
                            on_start=lambda r=result: motion and motion.express(r.emotion, r.intensity))
                        if motion:
                            motion.wait()
                    except Exception as exc:
                        print(f"[{choice.skill}] 실행 오류: {type(exc).__name__}: {exc}")
                        say("요청한 기능을 실행하지 못했어요. 설정과 연결 상태를 확인해 주세요.")
                    continue

                try:
                    reply = chat.send(text, on_search=on_search)
                except Exception as exc:
                    print(f"[llm] 응답 실패: {type(exc).__name__}: {exc}")
                    continue
                say(reply.answer,
                    on_start=lambda: motion and motion.express(reply.emotion, reply.intensity))
                if motion:
                    motion.wait()
        except KeyboardInterrupt:
            print("\n종료")
        finally:
            tts.stop()


if __name__ == "__main__":
    main()
