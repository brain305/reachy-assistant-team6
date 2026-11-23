"""Slack Incoming Webhook 전송. TTS용 일반 텍스트를 Slack mrkdwn으로 변환."""
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()


def format_slack_summary(summary: str) -> str:
    """뉴스 요약 본문은 평문으로 유지하고, Slack 전용 *굵게* 표기를 적용."""
    # 기존 LLM이 돌려준 Markdown **굵게**는 Slack의 *굵게*로 변환한다.
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", summary)
    # 현재 TTS 프롬프트가 만드는 문장형 제목을 Slack에서만 강조한다.
    text = re.sub(r"(?m)^(첫 번째|두 번째|세 번째|네 번째|다섯 번째) 기사\s*:\s*([^\n.]+)",
                  lambda m: f"*{m.group(1)} 기사: {m.group(2).strip()}*", text)
    return text


def send_to_slack(summary: str, links: str) -> bool:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")

    message = (
        "*Reachy Mini - IT 뉴스 요약*\n\n"
        + format_slack_summary(summary)
        + "\n\n*기사 출처*\n"
        + links
    )
    response = requests.post(webhook_url, json={"text": message}, timeout=15)
    response.raise_for_status()
    if response.text.strip() != "ok":
        raise RuntimeError(f"Slack 오류: {response.text}")
    return True
