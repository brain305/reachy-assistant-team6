"""API 키가 필요하며 Skill 분류만 검사한다. 실제 촬영/전송은 수행하지 않음."""

from skills.router import SkillRouter

router = SkillRouter()
for utterance in [
    "카메라 관련 정보를 알려줘",
    "지금 손에 들고 있는 물건이 뭐야?",
    "오늘 IT 뉴스 세 개 읽어 줘",
    "방금 요약한 뉴스를 슬랙으로 보내줘",
    "슬랙 웹훅 설정 방법 설명해 줘",
]:
    result = router.choose(utterance, has_news=True)
    print(f"{utterance} => {result.skill} ({result.query})")
