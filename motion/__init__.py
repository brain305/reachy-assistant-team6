"""감정별 Reachy 모션.

from reachy_mini import ReachyMini
from motion import EmotionMotion
with ReachyMini(media_backend="no_media") as mini:
    motion = EmotionMotion(mini)
    motion.express(Emotion.HAPPY, 0.8)            # 백그라운드에서 실행 (TTS와 동시에)
    motion.express("sad", 0.5, wait=True)         # 끝날 때까지 기다림

좌표 규칙 (시뮬레이터에서 확인)
  head pitch  + : 고개 숙임      - : 고개 듦
  head roll   + : 로봇 기준 오른쪽으로 갸우뚱
  head yaw    + : 로봇 기준 왼쪽을 봄
  antennas [왼쪽, 오른쪽] 라디안. 똑바로 선 기본값 [-0.17, 0.17],
           왼쪽은 더 음수, 오른쪽은 더 양수일수록 뒤로 눕는다 (수면 자세 [-3.05, 3.05])
"""

import threading
import time

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from llm.schema import Emotion

__all__ = ["EmotionMotion"]

_REST_ANTENNA = 0.17  # 기본 자세에서 안테나가 살짝 벌어진 각도 (떨림 방지용, SDK 기본값)


def _ant(left: float, right: float) -> list[float]:
    """안테나를 '세운 상태(0)에서 뒤로 눕힌 정도'로 지정. 0=똑바로, 클수록 뒤로 눕힘, 음수=앞으로."""
    return [-left, right]


REST_ANTENNAS = _ant(_REST_ANTENNA, _REST_ANTENNA)


def _head(roll: float = 0, pitch: float = 0, yaw: float = 0, z: float = 0):
    return create_head_pose(z=z, roll=roll, pitch=pitch, yaw=yaw, mm=True, degrees=True)


class EmotionMotion:
    def __init__(self, mini: ReachyMini):
        self.mini = mini
        self._thread: threading.Thread | None = None
        self._moves = {
            Emotion.HAPPY: self._happy,
            Emotion.SAD: self._sad,
            Emotion.CURIOUS: self._curious,
            Emotion.SURPRISED: self._surprised,
            Emotion.COMFORTING: self._comforting,
            Emotion.NEUTRAL: self._neutral,
        }

    # ---------- 공개 API ----------

    def express(self, emotion: Emotion | str, intensity: float = 0.5, wait: bool = False) -> None:
        """감정 모션 실행. 이전 모션이 진행 중이면 끝난 뒤 실행."""
        emotion = Emotion(emotion)
        k = 0.5 + 0.5 * max(0.0, min(1.0, intensity))  # 세기 0~1 → 동작 크기 0.5~1.0배
        self.wait()
        self._thread = threading.Thread(target=self._run, args=(emotion, k), daemon=True)
        self._thread.start()
        if wait:
            self.wait()

    def wait(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def rest(self, duration: float = 0.6) -> None:
        self.mini.goto_target(_head(), antennas=REST_ANTENNAS, body_yaw=0.0, duration=duration)

    # ---------- 내부 ----------

    def _run(self, emotion: Emotion, k: float) -> None:
        try:
            self._moves[emotion](k)
            self.rest()
        except Exception as e:  # 모션 실패로 대화가 멈추지 않게
            print(f"[motion] {emotion.value} 실패: {type(e).__name__}: {e}")

    def _go(self, head=None, antennas=None, body_deg: float = 0.0, duration: float = 0.3) -> None:
        self.mini.goto_target(
            head=head, antennas=antennas, body_yaw=body_deg * 3.14159 / 180, duration=duration
        )

    def _happy(self, k: float) -> None:
        # 고개를 살짝 들고, 안테나를 빠르게 파닥이며 몸을 좌우로 들썩
        a = 0.6 * k
        for i in range(3):
            side = 1 if i % 2 == 0 else -1
            self._go(_head(pitch=-8 * k, roll=4 * k * side), _ant(-a, -a), body_deg=10 * k * side, duration=0.2)
            self._go(_head(pitch=-8 * k), _ant(a, a), body_deg=0, duration=0.2)

    def _sad(self, k: float) -> None:
        # 천천히 고개를 숙이고 안테나를 축 늘어뜨림
        droop = _REST_ANTENNA + 1.4 * k
        self._go(_head(pitch=18 * k, z=-8 * k), _ant(droop, droop), duration=1.2)
        time.sleep(1.2)
        self._go(_head(pitch=12 * k, z=-6 * k), _ant(droop - 0.2, droop - 0.2), duration=0.8)

    def _curious(self, k: float) -> None:
        # 고개 갸우뚱 + 한쪽 안테나만 쫑긋
        self._go(_head(roll=-20 * k, yaw=8 * k), _ant(-0.2, 0.8 * k), duration=0.5)
        time.sleep(1.0)
        self._go(_head(roll=-14 * k, yaw=4 * k), _ant(-0.1, 0.6 * k), duration=0.4)

    def _surprised(self, k: float) -> None:
        # 순간적으로 고개를 뒤로 젖히고 안테나를 앞으로 확 세움
        self._go(_head(pitch=-14 * k, z=10 * k), _ant(-0.4 * k, -0.4 * k), duration=0.15)
        time.sleep(0.8)
        self._go(_head(pitch=-6 * k, z=4 * k), _ant(-0.2 * k, -0.2 * k), duration=0.4)

    def _comforting(self, k: float) -> None:
        # 안테나를 살짝 눕히고 천천히 두 번 끄덕
        soft = _REST_ANTENNA + 0.5 * k
        for _ in range(2):
            self._go(_head(pitch=12 * k, roll=5 * k), _ant(soft, soft), duration=0.7)
            self._go(_head(pitch=2, roll=5 * k), _ant(soft - 0.2, soft - 0.2), duration=0.7)

    def _neutral(self, k: float) -> None:
        # 정보 전달용. 가장 자주 나오는 감정이라 차분하지만 눈에 띄게:
        # 고개를 살짝 기울이며 안테나를 앞으로 톡 → 두 번 끄덕 → 몸을 살짝 돌렸다 복귀
        self._go(_head(roll=8 * k, yaw=6 * k), _ant(-0.3 * k, -0.3 * k), body_deg=8 * k, duration=0.35)
        for _ in range(2):
            self._go(_head(pitch=14 * k, roll=8 * k, yaw=6 * k), _ant(0.4 * k, 0.4 * k), body_deg=8 * k, duration=0.3)
            self._go(_head(pitch=-2, roll=8 * k, yaw=6 * k), _ant(-0.1, -0.1), body_deg=8 * k, duration=0.3)
        time.sleep(0.3)
