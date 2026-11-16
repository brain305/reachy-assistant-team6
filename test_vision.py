
from vision import recognize_object
from tts import TextToSpeech

print("카메라 앞에 물건을 들어 주세요.")
input("준비되면 Enter를 누르세요.")

answer = recognize_object()

print("Reachy:", answer)

tts = TextToSpeech()
tts.speak(answer)
