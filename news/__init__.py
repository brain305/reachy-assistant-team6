
import calendar
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

from llm import generate_text

RSS_URL = "https://techcrunch.com/feed/"


def get_latest_news(count=3):
    feed = feedparser.parse(RSS_URL)

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

    return summary, links
