
# Reachy Mini 개인 비서
# 기능: 음성 대화 + 감정 표현 + 시각 정보 인식
#       IT 영어 뉴스 요약 + Slack 전송
#
# 터미널 1: reachy-mini-daemon --sim
# 터미널 2: python voice_chat.py
# 종료: Ctrl+C

import time
from contextlib import nullcontext

from reachy_mini import ReachyMini

from llm import ReachyChat
from motion import EmotionMotion
from stt import SpeechToText
from tts import TextToSpeech
from vision import recognize_object
from news import summarize_news
from news.slack_sender import send_to_slack


# =====================================
# 1. Reachy Mini 연결
# =====================================

def connect_reachy():
    try:
        return ReachyMini(
            media_backend="no_media",
            timeout=3.0
        )
    except Exception as e:
        print(
            f"[motion] Reachy 연결 실패 → "
            f"모션 없이 진행 ({type(e).__name__}: {e})"
        )
        return None


print("STT 모델 불러오는 중...")

stt = SpeechToText()
tts = TextToSpeech()
chat = ReachyChat()

# 마지막으로 요약한 뉴스 저장
last_news = None

mini = connect_reachy()


# =====================================
# 2. 음성 출력
# =====================================

def say(text: str, wait: bool = True, on_start=None) -> None:
    print(f"Reachy: {text}")

    try:
        speech = tts.synthesize(text)
    except Exception as e:
        print(
            f"[tts] 음성 출력 실패: "
            f"{type(e).__name__}: {e}"
        )
        speech = None

    if on_start:
        on_start()

    if speech is not None:
        tts.play(speech, wait=wait)


# =====================================
# 3. 메인 프로그램
# =====================================

with mini if mini else nullcontext():

    motion = EmotionMotion(mini) if mini else None

    def on_search(r):
        print(f"  (검색: {chat.last_search_query})")

        say(
            r.answer,
            wait=False,
            on_start=lambda: motion and motion.express(
                "curious", 0.5
            )
        )

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

            # =====================================
            # 4. STT: 음성 → 텍스트
            # =====================================

            try:
                text = stt.transcribe(audio)

            except Exception as e:
                print(
                    f"[stt] 인식 실패: "
                    f"{type(e).__name__}: {e}"
                )
                continue

            if not text:
                continue

            t1 = time.time()

            print(f"나: {text}")

            # 음성 인식 결과 정규화
            normalized_text = text.lower().replace(" ", "")

            # =====================================
            # 5. 시각 정보 인식
            # =====================================

            if (
                (
                    "손에" in text
                    or "들고" in text
                    or "카메라" in text
                )
                and (
                    "뭐" in text
                    or "무엇" in text
                    or "보여" in text
                    or "알려" in text
                )
            ):
                try:
                    print("[Vision] 카메라로 물체를 인식합니다.")

                    answer = recognize_object(text)

                    say(
                        answer,
                        on_start=lambda: motion and motion.express(
                            "curious", 0.7
                        )
                    )

                    if motion:
                        motion.wait()

                except Exception as e:
                    print(
                        f"[Vision 오류] "
                        f"{type(e).__name__}: {e}"
                    )
                    say("미안해요. 물체를 인식하지 못했어요.")

                continue

            # =====================================
            # 6. Slack 뉴스 전송
            # =====================================
            # 뉴스 요약 기능보다 먼저 검사해야 함

            slack_requested = (
                "슬랙" in normalized_text
                or "slack" in normalized_text
                or "슬렉" in normalized_text
            )

            send_requested = (
                "보내" in text
                or "전송" in text
                or "공유" in text
            )

            if slack_requested and send_requested:

                try:
                    if last_news is None:
                        say(
                            "아직 요약한 뉴스가 없어요. "
                            "먼저 IT 뉴스를 알려달라고 해주세요."
                        )

                    else:
                        summary, links = last_news

                        print(
                            "[Slack] 최근 IT 뉴스 요약을 "
                            "전송합니다."
                        )

                        send_to_slack(summary, links)

                        say(
                            "방금 요약한 뉴스와 기사 링크를 "
                            "슬랙으로 전송했어요.",
                            on_start=lambda: motion and motion.express(
                                "happy", 0.6
                            )
                        )

                        if motion:
                            motion.wait()

                except Exception as e:
                    print(
                        f"[Slack 오류] "
                        f"{type(e).__name__}: {e}"
                    )
                    say(
                        "미안해요. 슬랙으로 전송하는 데 "
                        "문제가 발생했어요."
                    )

                continue

            # =====================================
            # 7. IT 영어 뉴스 요약
            # =====================================

            news_requested = (
                "뉴스" in text
                or "기사" in text
            )

            if news_requested:

                try:
                    print(
                        "[News] 최신 IT 영어 뉴스를 검색합니다."
                    )

                    say("최신 IT 뉴스를 찾아볼게요.")

                    # 영어 기사 수집 + Gemini 요약
                    summary, links = summarize_news()

                    # 최근 뉴스 저장
                    last_news = (summary, links)

                    print(
                        "\n========== IT 뉴스 요약 =========="
                    )
                    print(summary)

                    print(
                        "\n========== 기사 출처 =========="
                    )
                    print(links)

                    # 뉴스 음성 출력 + 감정 표현
                    say(
                        summary,
                        on_start=lambda: motion and motion.express(
                            "happy", 0.5
                        )
                    )

                    if motion:
                        motion.wait()

                except Exception as e:
                    print(
                        f"[News 오류] "
                        f"{type(e).__name__}: {e}"
                    )

                    say(
                        "미안해요. 최신 IT 뉴스를 "
                        "가져오지 못했어요."
                    )

                continue

            # =====================================
            # 8. 일반 LLM 음성 대화
            # =====================================

            try:
                reply = chat.send(
                    text,
                    on_search=on_search
                )

            except Exception as e:
                print(
                    f"[llm] 응답 실패: "
                    f"{type(e).__name__}: {e}"
                )
                continue

            t2 = time.time()

            print(
                f"  감정={reply.emotion.value} "
                f"세기={reply.intensity:.1f}"
            )

            print(
                f"  (STT {t1 - t0:.1f}s + "
                f"LLM {t2 - t1:.1f}s = "
                f"대답까지 {t2 - t0:.1f}s)"
            )

            say(
                reply.answer,
                on_start=lambda: motion and motion.express(
                    reply.emotion,
                    reply.intensity
                )
            )

            if motion:
                motion.wait()

    except KeyboardInterrupt:
        tts.stop()
        print("\n종료")
