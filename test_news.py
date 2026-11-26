
from news import summarize_news
from tts import TextToSpeech

print("최신 IT 영어 기사를 수집하고 있습니다...")

summary, links = summarize_news()

print("\n========== IT 뉴스 요약 ==========")
print(summary)

print("\n========== 기사 출처 ==========")
print(links)

print("\nReachy가 뉴스를 읽어 줍니다.")

tts = TextToSpeech()
tts.speak(summary)

print("\n뉴스 요약 완료!")
