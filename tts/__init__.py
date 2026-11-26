"""TTS 모듈 (edge-tts: Microsoft Edge 온라인 음성, API 키 불필요, 인터넷 필요).

from tts import TextToSpeech
tts = TextToSpeech()
tts.speak("안녕, 난 리치야")        # 다 읽을 때까지 기다림
audio = tts.synthesize("안녕")      # 재생하지 않고 오디오만 (float32, tts.sample_rate)

.env 로 바꿀 수 있는 값
  TTS_VOICE  ko-KR-SunHiNeural(기본, 여성) / ko-KR-InJoonNeural(남성) / ko-KR-HyunsuMultilingualNeural(남성)
  TTS_RATE   말 빠르기. 예: +10%, -10%
"""

import asyncio
import io
import os
import re

import av
import edge_tts
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

DEFAULT_VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%")
SAMPLE_RATE = 24000  # edge-tts 기본 출력(24kHz mp3)

__all__ = ["TextToSpeech", "SAMPLE_RATE", "clean_for_speech"]


def clean_for_speech(text: str) -> str:
    """LLM 답변의 마크다운 기호(**강조**, # 제목, - 목록, `코드`, [링크](url))를 TTS가 읽지 않게 지운다."""
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)      # [글자](링크) → 글자
    text = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda m: m.group(1) or m.group(2) or "", text, flags=re.S)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)                     # # 제목
    text = re.sub(r"(?m)^\s{0,3}>\s?", "", text)                          # > 인용
    text = re.sub(r"(?m)^\s*[-*+•]\s+", "", text)                          # - 목록
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)             # *기울임*
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)                     # `코드`
    text = re.sub(r"\*{2,}|_{2,}|#{2,}", "", text)                         # 짝이 안 맞고 남은 기호
    return text.strip()


def _decode_mp3(data: bytes, sample_rate: int) -> np.ndarray:
    """mp3 바이트 → mono float32 배열."""
    resampler = av.AudioResampler(format="flt", layout="mono", rate=sample_rate)
    chunks = []
    with av.open(io.BytesIO(data)) as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # 남은 샘플 비우기
            chunks.append(out.to_ndarray().reshape(-1))
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)



class TextToSpeech:
    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        device: int | str | None = None,
    ):
        """device: 스피커 장치 번호나 이름 (None이면 시스템 기본 스피커)"""
        self.voice = voice
        self.rate = rate
        self.device = device
        self.sample_rate = SAMPLE_RATE

    async def _fetch_mp3(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        buf = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    def synthesize(self, text: str) -> np.ndarray:
        """텍스트 → 오디오 배열 (재생은 안 함). 나중에 Reachy 스피커로 보낼 때 사용."""
        text = clean_for_speech(text)  # 모든 기능의 답변이 여기를 거치므로 마크다운을 한 곳에서 제거
        if not text:
            return np.zeros(0, dtype=np.float32)
        mp3 = asyncio.run(self._fetch_mp3(text))
        return _decode_mp3(mp3, self.sample_rate)

    def play(self, audio: np.ndarray, wait: bool = True) -> None:
        """오디오 배열을 재생한다. 앞에서 재생 중인 소리가 있으면 끝난 뒤에 재생.
        wait=False면 재생을 시작만 하고 바로 돌아온다 (검색하는 동안 "잠깐 찾아볼게" 재생 등).
        """
        sd.wait()
        if audio.size:
            sd.play(audio, self.sample_rate, device=self.device)
            if wait:
                sd.wait()

    def speak(self, text: str, wait: bool = True) -> None:
        """텍스트를 읽어준다. 기본은 다 읽을 때까지 기다림 (그동안 마이크가 Reachy 목소리를 듣지 않게)."""
        text = text.strip()
        if text:
            self.play(self.synthesize(text), wait=wait)

    def stop(self) -> None:
        sd.stop()
