"""TTS 마크다운 정리 단위 테스트 (네트워크·스피커 불필요).

python -m unittest test_tts_clean -v
"""

import unittest

from tts import clean_for_speech


class CleanForSpeechTests(unittest.TestCase):
    def check(self, raw, expected):
        self.assertEqual(clean_for_speech(raw), expected)

    def test_bold(self):
        self.check("이건 **텀블러**예요.", "이건 텀블러예요.")

    def test_multiline_bold_and_heading(self):
        self.check("## 오늘의 일기\n**알찬 하루**였다.", "오늘의 일기\n알찬 하루였다.")

    def test_list_and_italic(self):
        self.check("- 첫째: *현대대수*\n* 둘째: 해석학", "첫째: 현대대수\n둘째: 해석학")

    def test_link_and_code(self):
        self.check("[TechCrunch](https://techcrunch.com) 기사, `GPT` 모델", "TechCrunch 기사, GPT 모델")

    def test_unpaired_symbols_removed(self):
        self.check("**강조가 안 닫힘", "강조가 안 닫힘")

    def test_plain_text_unchanged(self):
        self.check("안녕! 3*4는 12야.", "안녕! 3*4는 12야.")

    def test_only_symbols_becomes_empty(self):
        self.check("**  **", "")


if __name__ == "__main__":
    unittest.main()
