# STT 테스트. 말을 하면 자동으로 감지해서 텍스트로 출력한다. (Ctrl+C로 종료)
#
# python test_stt.py          # 마이크로 테스트
# python test_stt.py a.wav    # 오디오 파일 변환

import sys
import time

from stt import SpeechToText

print("STT 모델 불러오는 중... (첫 실행은 다운로드 때문에 오래 걸림)")
stt = SpeechToText()

if len(sys.argv) > 1:
    print(stt.transcribe(sys.argv[1]))
    sys.exit()

print("말해 보세요. 말을 멈추면 자동으로 인식합니다. (Ctrl+C로 종료)")
try:
    while True:
        print("\n듣는 중...")
        t0 = time.time()
        text = stt.listen()
        if text:
            print(f"인식: {text}  ({time.time() - t0:.1f}s)")
except KeyboardInterrupt:
    pass
