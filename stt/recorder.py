"""마이크에서 한 문장(발화)을 자동으로 잘라 녹음한다.

말을 시작하면 녹음을 시작하고, 일정 시간 조용하면 녹음을 끝낸다.
"""

import queue
from collections import deque
from collections.abc import Iterable, Iterator

import numpy as np
import sounddevice as sd

from .vad import FRAME_SIZE, SAMPLE_RATE, StreamingVAD

FRAME_MS = FRAME_SIZE * 1000 // SAMPLE_RATE  # 32ms


def _ms_to_frames(ms: int) -> int:
    return max(1, ms // FRAME_MS)


def segment_utterance(
    frames: Iterable[np.ndarray],
    vad: StreamingVAD,
    start_threshold: float = 0.5,
    end_threshold: float = 0.35,
    silence_ms: int = 800,
    min_speech_ms: int = 300,
    pre_roll_ms: int = 300,
    max_speech_s: float = 30.0,
) -> np.ndarray | None:
    """프레임 스트림에서 첫 번째 발화 구간을 잘라 돌려준다.

    마이크와 분리해 두어서 파일 오디오로도 테스트할 수 있다.
    스트림이 끝날 때까지 발화가 없으면 None.
    """
    vad.reset()
    pre_roll: deque[np.ndarray] = deque(maxlen=_ms_to_frames(pre_roll_ms))
    speech: list[np.ndarray] = []
    voiced_frames = 0
    silent_frames = 0
    silence_limit = _ms_to_frames(silence_ms)
    max_frames = _ms_to_frames(int(max_speech_s * 1000))

    for frame in frames:
        prob = vad(frame)

        if not speech:  # 아직 말 시작 전
            pre_roll.append(frame)
            if prob >= start_threshold:
                speech = list(pre_roll)  # 말 앞부분이 잘리지 않게 직전 소리 포함
                voiced_frames = 1
                silent_frames = 0
            continue

        speech.append(frame)
        if prob >= end_threshold:
            voiced_frames += 1
            silent_frames = 0
        else:
            silent_frames += 1

        if silent_frames >= silence_limit or len(speech) >= max_frames:
            if voiced_frames >= _ms_to_frames(min_speech_ms):
                return np.concatenate(speech)
            # 기침, 책상 치는 소리처럼 너무 짧은 소리는 버리고 다시 대기
            speech, voiced_frames, silent_frames = [], 0, 0
            pre_roll.clear()
            vad.reset()

    if speech and voiced_frames >= _ms_to_frames(min_speech_ms):
        return np.concatenate(speech)
    return None


def _mic_frames(device: int | str | None, timeout_s: float | None) -> Iterator[np.ndarray]:
    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, _frames, _time, status):
        if status:
            print(f"[mic] {status}")
        q.put(indata[:, 0].copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SIZE,
        channels=1,
        dtype="float32",
        device=device,
        callback=callback,
    ):
        waited = 0.0
        while timeout_s is None or waited < timeout_s:
            yield q.get()
            waited += FRAME_SIZE / SAMPLE_RATE


def record_utterance(
    vad: StreamingVAD,
    device: int | str | None = None,
    timeout_s: float | None = None,
    **kwargs,
) -> np.ndarray | None:
    """마이크로 한 문장을 녹음해서 16kHz float32 배열로 돌려준다.

    timeout_s 동안 말이 끝나지 않으면 None (None이면 무한 대기).
    """
    return segment_utterance(_mic_frames(device, timeout_s), vad, **kwargs)
