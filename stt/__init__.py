"""로컬 STT 모듈 (faster-whisper + Silero VAD 자동 발화 감지).

from stt import SpeechToText
stt = SpeechToText()
text = stt.listen()          # 말이 끝날 때까지 듣고 텍스트로 변환
text = stt.transcribe(audio) # 16kHz float32 배열 또는 파일 경로를 변환
"""

import os

import ctranslate2
import numpy as np
from dotenv import load_dotenv
from faster_whisper import WhisperModel

from .recorder import record_utterance, segment_utterance
from .vad import FRAME_SIZE, SAMPLE_RATE, StreamingVAD

load_dotenv()

DEFAULT_MODEL = os.getenv("STT_MODEL", "large-v3-turbo")

__all__ = ["SpeechToText", "StreamingVAD", "segment_utterance", "SAMPLE_RATE", "FRAME_SIZE"]


def _pick_device() -> tuple[str, str]:
    """NVIDIA GPU(WSL) → cuda, 그 외(Mac 포함) → cpu.
    .env 에 STT_DEVICE=cpu 처럼 적으면 강제로 지정할 수 있다.

    Mac GPU(mps)는 ctranslate2 4.9에서 실험 기능이라 자동 선택하지 않는다.
    재시도(temperature fallback)가 일어나는 입력에서 IndexError: vector 로 자주 실패함.
    """
    forced = os.getenv("STT_DEVICE")
    types = {"cuda": "float16", "mps": "float16", "cpu": "int8"}
    if forced in types:
        return forced, types[forced]
    if ctranslate2.get_cuda_device_count() > 0:
        return "cuda", "float16"
    return "cpu", "int8"


class SpeechToText:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        language: str = "ko",
        device: int | str | None = None,
    ):
        """model: tiny / base / small / medium / large-v3 / large-v3-turbo
        device: 마이크 장치 번호나 이름 (None이면 시스템 기본 마이크)
        첫 실행 시 모델을 Hugging Face에서 내려받는다.
        """
        compute_device, compute_type = _pick_device()
        self.model = WhisperModel(model, device=compute_device, compute_type=compute_type)
        self.language = language
        self.mic_device = device
        self.vad = StreamingVAD()

    def transcribe(self, audio: np.ndarray | str) -> str:
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # 남은 무음 구간 제거 → 무음에서 엉뚱한 문장이 생기는 것 방지
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def record(self, timeout_s: float | None = None, **vad_kwargs) -> np.ndarray | None:
        """마이크로 한 문장을 녹음만 한다 (16kHz float32). 말이 없으면 None."""
        return record_utterance(self.vad, device=self.mic_device, timeout_s=timeout_s, **vad_kwargs)

    def listen(self, timeout_s: float | None = None, **vad_kwargs) -> str | None:
        """마이크로 한 문장을 듣고 텍스트로 변환. 말이 없거나 인식 결과가 비면 None."""
        audio = self.record(timeout_s=timeout_s, **vad_kwargs)
        if audio is None:
            return None
        try:
            return self.transcribe(audio) or None
        except Exception as e:  # 인식 한 번 실패로 대화 전체가 꺼지지 않게
            print(f"[stt] 인식 실패, 다시 말해 주세요: {type(e).__name__}: {e}")
            return None
