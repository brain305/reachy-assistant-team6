"""Reachy Mini: STT → LLM Skill 라우팅 → 실행 결과 TTS/감정 모션.

터미널 1: reachy-mini-daemon --sim
터미널 2: python voice_chat.py
"""

import time
from contextlib import nullcontext

from reachy_mini import ReachyMini
from diary.conversation import DiaryConversation, spoken_text
from motion import EmotionMotion
from skills.router import SkillRouter
from skills.runner import SkillRunner
from stt import SpeechToText
from tts import TextToSpeech


def connect_reachy():
    # media_backend="no_media": 마이크·스피커는 우리 STT/TTS가 쓰므로 SDK가 잡지 않게 함
    try:
        return ReachyMini(media_backend="no_media", timeout=3.0)
    except Exception as exc:
        print(f"[motion] Reachy 연결 실패 → 모션 없이 진행: {exc}")
        return None


def main():
    print("STT 모델 불러오는 중...")
    stt = SpeechToText()
    tts = TextToSpeech()
    chat = DiaryConversation()  # 일반 대화 + 일기 기능 (대화 기록은 프로그램을 껐다 켜면 초기화)
    router = SkillRouter()
    runner = SkillRunner()
    mini = connect_reachy()

    def say(text: str, wait: bool = True, on_start=None):
        # 음성을 먼저 생성한 뒤 on_start(모션)와 재생을 함께 시작해 타이밍을 맞춘다.
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
                audio = stt.record()  # Reachy가 말하는 동안에는 듣지 않음
                if audio is None:
                    continue
                # 여기부터 사용자가 말을 마친 뒤 응답까지 걸리는 시간을 측정
                t0 = time.time()
                try:
                    text = stt.transcribe(audio)
                except Exception as exc:
                    print(f"[stt] 인식 실패: {type(exc).__name__}: {exc}")
                    continue
                if not text:
                    continue
                t1 = time.time()
                print(f"나: {text}")
                print(f"  (STT {t1 - t0:.1f}s)")

                choice = None
                if chat.diary.active or chat.diary.pending_start:
                    # 일기 작성 중인 발화는 카메라/뉴스 스킬로 새지 않도록 라우터를 건너뛴다.
                    print("[Skill Router] 일기 진행 중 → chat")
                else:
                    try:
                        choice = router.choose(text, has_news=runner.last_news is not None)
                        t_router = time.time()
                        print(f"[Skill Router] {choice.skill} (라우팅 {t_router - t1:.1f}s)")
                    except Exception as exc:
                        print(f"[Router] 판단 실패 → 일반 대화: {type(exc).__name__}: {exc}")

                if choice and choice.skill != "chat":
                    try:
                        t_skill = time.time()
                        result = runner.execute(choice.skill, choice.query or text)
                        t_skill_done = time.time()
                        print(f"  감정={result.emotion} 세기={result.intensity:.1f}")
                        print(f"  (STT {t1 - t0:.1f}s + 라우팅 {t_skill - t1:.1f}s + Skill {t_skill_done - t_skill:.1f}s = 대답까지 {t_skill_done - t0:.1f}s)")
                        say(result.answer,
                            on_start=lambda r=result: motion and motion.express(r.emotion, r.intensity))
                        if motion:
                            motion.wait()
                    except Exception as exc:
                        print(f"[{choice.skill}] 실행 오류: {type(exc).__name__}: {exc}")
                        say("요청한 기능을 실행하지 못했어요. 설정과 연결 상태를 확인해 주세요.")
                    continue

                try:
                    t_llm = time.time()
                    reply = chat.send(text, on_search=on_search)
                except Exception as exc:
                    print(f"[llm] 응답 실패: {type(exc).__name__}: {exc}")
                    continue
                t_done = time.time()
                emotion_name = getattr(reply.emotion, "value", reply.emotion)
                print(f"  감정={emotion_name} 세기={reply.intensity:.1f}")
                print(f"  (STT {t1 - t0:.1f}s + 라우팅 {t_llm - t1:.1f}s + LLM {t_done - t_llm:.1f}s = 대답까지 {t_done - t0:.1f}s)")
                say(spoken_text(reply),
                    on_start=lambda: motion and motion.express(reply.emotion, reply.intensity))
                if motion:
                    motion.wait()  # 모션이 끝난 뒤 다시 듣기
        except (KeyboardInterrupt, EOFError):
            print("\n종료")
        finally:
            tts.stop()
            chat.close()  # 저장하지 않은 일기 내용이 있으면 출력


if __name__ == "__main__":
    main()
