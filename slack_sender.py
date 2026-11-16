
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_to_slack(summary, links):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError("Slack Webhook URL이 없습니다.")

    message = (
        "*Reachy Mini - 오늘의 IT 뉴스*\n\n"
        + summary
        + "\n\n*기사 출처*\n"
        + links
    )

    response = requests.post(
        webhook_url,
        json={"text": message},
        timeout=15
    )

    response.raise_for_status()

    if response.text.strip() != "ok":
        raise RuntimeError(f"Slack 응답 오류: {response.text}")

    return True