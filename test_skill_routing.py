"""로봇/LLM API 없이 실행할 수 있는 Skill 실행기 테스트."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
