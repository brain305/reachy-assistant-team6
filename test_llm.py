# LLM 모듈 테스트. STT 대신 키보드로 입력하고, 대답과 감정을 JSON으로 출력한다.

# python test_llm.py            # 대화 모드 (빈 줄 또는 Ctrl+C로 종료)
#

from llm import ReachyChat

chat = ReachyChat()
print("Reachy와 대화를 시작합니다. (빈 줄 입력 시 종료)")

try:
    while True:
        user_text = input("\n나: ").strip()
        if not user_text:
            break
        reply = chat.send(user_text)
        print(reply.model_dump_json(indent=2))
except (KeyboardInterrupt, EOFError):
    pass
