from news.slack_sender import send_to_slack

print("Slack 메시지 전송 테스트 중...")

send_to_slack(
    "Reachy Mini에서 보낸 테스트 메시지입니다!",
    "테스트 메시지 - 실제 기사 링크 없음"
)

print("Slack 전송 성공!")
