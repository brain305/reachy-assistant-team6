# LLM 모듈 테스트. STT 대신 키보드로 입력하고, 대답과 감정을 JSON으로 출력한다.

# python test_llm.py            # 대화 모드 (빈 줄 또는 Ctrl+C로 종료)
# python test_llm.py --skill    # skill 판단 확인. 프롬프트를 고친 뒤 돌려 보기 (Gemini 호출 약 6번)
#

import sys

import llm
from llm import ReachyChat

# (사용자 말, 기대 결과). 기대 결과의 "+search"는 chat이면서 검색어가 채워져야 한다는 뜻
SKILL_CASES = [
    ("오늘 IT 뉴스 알려줘", "news"),
    ("이거 무슨 색이야?", "vision"),
    ("오늘 일기 써줘", "diary"),
    ("오늘 서울 날씨 어때?", "chat+search"),
    ("나 오늘 피곤해", "chat"),
    ("어제 축구 경기 결과 알려줘", "chat+search"),
]


def check_skills():
    # 첫 판단만 확인하므로 실제 검색은 막는다 (호출 절약)
    llm.search_web = lambda query, model=None: "(테스트: 검색 생략)"
    failed = 0
    for text, want in SKILL_CASES:
        searched = []
        reply = ReachyChat().send(text, on_search=lambda r: searched.append(r.search_query))
        got = reply.skill.value + ("+search" if searched else "")
        ok = got == want
        failed += not ok
        print(f"{'OK' if ok else 'XX'}  {text} → {got} (기대: {want}) | skill_query={reply.skill_query!r}")
    print(f"\n{len(SKILL_CASES) - failed}/{len(SKILL_CASES)} 통과")
    sys.exit(1 if failed else 0)


if sys.argv[1:] == ["--skill"]:
    check_skills()

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
