"""로봇/LLM API 없이 실행할 수 있는 Skill + 라우팅 단위 테스트."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch


from skills.runner import SkillRunner


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.runner = SkillRunner(
            recognize=lambda q: "인식: " + q,
            summarize=lambda: ("요약 결과", "https://example.com/article"),
            send=lambda summary, links: self.sent.append((summary, links)),
        )

    def test_vision(self):
        self.assertIn("텀블러", self.runner.execute("vision", "텀블러").answer)

    def test_news_then_slack(self):
        self.assertEqual(self.runner.execute("news").answer, "요약 결과")
        self.assertIn("전송", self.runner.execute("slack").answer)
        self.assertEqual(self.sent, [("요약 결과", "https://example.com/article")])

    def test_no_news_no_send(self):
        self.assertIn("먼저", self.runner.execute("slack").answer)
        self.assertEqual(self.sent, [])

    def test_invalid_skill(self):
        with self.assertRaises(ValueError):
            self.runner.execute("unregistered")


class RouterTests(unittest.TestCase):
    def test_router_parsed_result(self):
        from skills.router import SkillRouter, SkillChoice
        fake_client = SimpleNamespace(models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(
                parsed=SkillChoice(skill="chat", query=""), text=None)))
        result = SkillRouter(client=fake_client, model="mock").choose("카메라 기능 설명해 줘")
        self.assertEqual(result.skill, "chat")

    def test_runner_creation_does_not_import_optional_modules(self):
        import sys
        with patch.dict(sys.modules, {"vision": None, "news": None, "cv2": None}):
            runner = SkillRunner()
            self.assertIsNone(runner.recognize)
            self.assertIsNone(runner.summarize)
            self.assertEqual(runner.execute("slack").answer[:2], "아직")

    def test_markdown_cleanup(self):
        from news import clean_tts_text
        self.assertEqual(clean_tts_text("**첫 번째 기사**\n# 제목"), "첫 번째 기사\n제목")

    def test_news_feed_uses_timeout(self):
        from news import get_latest_news
        from unittest.mock import MagicMock
        import news
        fake_response = MagicMock(content=b"rss")
        fake_response.raise_for_status.return_value = None
        with patch.object(news.requests, "get", return_value=fake_response) as get, \
             patch.object(news.feedparser, "parse", return_value=SimpleNamespace(entries=[])) as parse:
            with self.assertRaises(RuntimeError):
                get_latest_news()
            self.assertEqual(get.call_args.kwargs["timeout"], (5, 12))
            parse.assert_called_once_with(b"rss")

    def test_slack_sender_uses_slack_format(self):
        from news.slack_sender import send_to_slack
        from unittest.mock import MagicMock
        response = MagicMock(text="ok")
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test"}), \
             patch("news.slack_sender.requests.post", return_value=response) as post:
            self.assertTrue(send_to_slack("**강조**", "https://example.com"))
            self.assertIn("*강조*", post.call_args.kwargs["json"]["text"])
            self.assertNotIn("**강조**", post.call_args.kwargs["json"]["text"])

    def test_slack_bold_format(self):
        from news.slack_sender import format_slack_summary
        self.assertEqual(format_slack_summary("첫 번째 기사: AI 모델 발표. 내용입니다."),
                         "*첫 번째 기사: AI 모델 발표*. 내용입니다.")


if __name__ == "__main__":
    unittest.main()
