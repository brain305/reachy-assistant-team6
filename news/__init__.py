"""TechCrunch RSS 기사 메타데이터 수집 및 TTS용 한국어 요약."""
import calendar
import re
from datetime import datetime, timezone

import requests
import feedparser
from bs4 import BeautifulSoup

from llm import generate_text

RSS_URL = "https://techcrunch.com/feed/"


def get_latest_news(count=3):
    # feedparser.parse(URL)은 자체적으로 요청 시간을 제한할 수 없으므로 먼저 받아서 파싱한다.
    response = requests.get(
        RSS_URL,
        headers={"User-Agent": "ReachyMini-News/1.0"},
        timeout=(5, 12),
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    if not feed.entries:
        raise RuntimeError("IT 뉴스를 가져오지 못했습니다.")

    articles = []

    for entry in feed.entries:
        date = entry.get("published_parsed")

        if date:
            published = datetime.fromtimestamp(
                calendar.timegm(date),
                tz=timezone.utc
            )
        else:
            published = None

        description = BeautifulSoup(
            entry.get("summary", ""), "html.parser"
        ).get_text(" ", strip=True)

        articles.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": published,
            "description": description[:1500],
        })

    # 발행 날짜 기준으로 정렬
    articles.sort(
        key=lambda a: a["published"]
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    return articles[:count]


def clean_tts_text(text: str) -> str:
    """LLM이 마크다운을 반환하더라도 TTS에는 장식 기호를 전달하지 않는다."""
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)`([^`]+)`(?!\w)", r"\1", text)
    return text.strip()


def summarize_news():
    articles = get_latest_news()

    source_text = "\n\n".join(
        f"제목: {a['title']}\n"
        f"발행: {a['published']}\n"
        f"내용: {a['description']}\n"
        f"링크: {a['link']}"
        for a in articles
    )

    prompt = f"""
다음 영어 IT 기사 정보를 한국어로 요약해 줘.

조건:
1. 기사별로 제목과 핵심 내용을 설명해.
2. 각 기사마다 2~3문장으로 요약해.
3. 어려운 IT 용어는 쉽게 설명해.
4. 제공된 정보에 없는 사실은 만들지 마.
5. Reachy가 음성으로 읽기 자연스럽게 작성해.
6. 기사 발행 시각이 오래되었으면 최신이라고 단정하지 마.
7. 음성 합성(TTS)으로 읽을 일반 문장만 작성해. 마크다운(**, *, #, -, 백틱), 이모지, 목록 장식 기호를 사용하지 마.
8. 각 기사를 '첫 번째 기사: 제목. 요약...' 같은 자연스러운 문장으로 시작해.

기사:
{source_text}
"""

    summary = generate_text(
        prompt,
        system="너는 최신 IT 뉴스를 설명하는 한국어 AI 비서야."
    )

    links = "\n".join(
        f"{a['title']}: {a['link']}"
        for a in articles
    )

    return clean_tts_text(summary), links
