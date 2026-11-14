"""실시간 음성 감지(VAD). faster-whisper에 들어 있는 Silero VAD 모델을 프레임 단위로 돌린다."""

import numpy as np
from faster_whisper.vad import get_vad_model

SAMPLE_RATE = 16000
FRAME_SIZE = 512  # 32ms. Silero VAD가 16kHz에서 요구하는 프레임 크기
_CONTEXT_SIZE = 64


class StreamingVAD:
    """512샘플 프레임을 하나씩 넣으면 '말하는 중일 확률(0~1)'을 돌려준다.

    faster-whisper의 SileroVADModel은 호출할 때마다 상태를 초기화해서
    한 번에 전체 오디오를 넣는 용도라, 마이크 스트리밍용으로 상태를 유지하는 버전을 따로 둔다.
    """

    def __init__(self):
        self._session = get_vad_model().session
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(_CONTEXT_SIZE, dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        if frame.shape != (FRAME_SIZE,):
            raise ValueError(f"frame은 길이 {FRAME_SIZE}의 1차원 배열이어야 합니다.")
        x = np.concatenate([self._context, frame.astype(np.float32)])[None, :]
        prob, self._h, self._c = self._session.run(
            None, {"input": x, "h": self._h, "c": self._c}
        )
        self._context = frame[-_CONTEXT_SIZE:].astype(np.float32)
        return float(prob[0])
