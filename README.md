# Reachy Mini 개인 비서 (딥러닝 6조)

Reachy Mini 시뮬레이터(MuJoCo) 위에서 동작하는 음성 대화형 개인 비서 프로젝트입니다.

- **기본 기능:** 음성 대화, 대화 내용에 따른 감정 표현(안테나·고개·몸통), 시각 정보 인식
- **추가 기능:** IT 영어 기사 요약, 감정 공감 및 일기 작성, 일정 관리, 학습 보조

현재 저장소에는 **기본 개발 환경 설정**과 동작 확인용 예제가 들어 있습니다.

## 요구 사항

| 항목 | 버전 |
|---|---|
| Python | 3.12 |
| 패키지 관리 | [uv](https://docs.astral.sh/uv/) |
| Reachy Mini SDK | `reachy-mini[mujoco]` 1.14.0 (`requirements.txt`) |
| OS | Windows + WSL2 (Ubuntu) 또는 macOS (Apple Silicon) |


---

## 설치: WSL (Ubuntu)

Ubuntu 26.04 / WSLg 환경에서 확인했습니다.

### 1. 시스템 패키지

```bash
sudo apt update
sudo apt install -y \
  git git-lfs build-essential pkg-config libcairo2-dev libgirepository1.0-dev \
  gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gir1.2-gst-plugins-bad-1.0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-nice gstreamer1.0-pulseaudio
git lfs install
```

| 패키지 | 필요한 이유 |
|---|---|
| `build-essential`, `pkg-config`, `libcairo2-dev`, `libgirepository1.0-dev` | SDK가 쓰는 `pygobject`를 리눅스에서 직접 컴파일하기 위해 |
| `gir1.2-gst*`, `gstreamer1.0-*` | 데몬이 카메라·오디오 처리에 쓰는 GStreamer |

### 2. uv 설치 (없는 경우)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 저장소 클론 + 가상환경

```bash
cd ~
git clone <저장소 URL> reachi
cd reachi
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python -c "from reachy_mini import ReachyMini; print('Reachy Mini SDK OK')"
```


### 4. GPU 렌더링 설정 (시뮬레이터 렉 방지)

WSL에서는 시뮬레이터가 GPU 대신 CPU(`llvmpipe`)로 화면을 그려 심하게 느려질 수 있습니다. GPU를 직접 지정합니다.

```bash
echo 'export GALLIUM_DRIVER=d3d12' >> ~/.bashrc
echo 'export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA' >> ~/.bashrc   # NVIDIA GPU인 경우
source ~/.bashrc
```

확인 (선택):

```bash
sudo apt install -y mesa-utils
glxinfo -B | grep renderer    # "D3D12 (...)"이면 GPU, "llvmpipe"면 CPU
```

### 5. VS Code 연결

1. Windows VS Code에 **WSL** 확장 설치
2. WSL 터미널에서 `code .` 실행 → 왼쪽 아래에 `WSL: Ubuntu` 표시 확인
3. 확장 탭에서 Python 확장을 **Install in WSL: Ubuntu**
4. `Ctrl+Shift+P` → `Python: Select Interpreter` → `Enter interpreter path...` → `./.venv/bin/python` 직접 입력

---

## 설치: macOS (Apple Silicon)

### 1. 기본 도구

```bash
xcode-select --install          # C 컴파일러 (팝업에서 설치)
# Homebrew가 없다면: https://brew.sh 의 설치 명령 실행
brew install uv git-lfs pkg-config cairo gobject-introspection gstreamer
git lfs install
```

| WSL | macOS |
|---|---|
| `build-essential` | Xcode Command Line Tools |
| `libcairo2-dev`, `libgirepository1.0-dev` | `brew install cairo gobject-introspection` |
| `gstreamer1.0-*` | `brew install gstreamer` |

### 2. 저장소 클론 + 가상환경 (WSL과 동일)

```bash
git clone <저장소 URL> reachi
cd reachi
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python -c "from reachy_mini import ReachyMini; print('Reachy Mini SDK OK')"
```

### 3. 시뮬레이터 실행 시 주의

macOS는 GUI 창을 메인 스레드에서만 띄울 수 있어서, MuJoCo 창이 뜨지 않으면 `mjpython`으로 실행해야 할 수 있습니다.

```bash
reachy-mini-daemon --sim                              # 먼저 시도
mjpython -m reachy_mini.daemon.app.main --sim         # 창이 안 뜨면 시도
```

정확한 명령은 SDK 버전에 따라 다를 수 있으니 [공식 저장소](https://github.com/pollen-robotics/reachy_mini) README의 macOS 안내를 확인하세요.

### 4. 권한

마이크·카메라를 쓸 때 **시스템 설정 → 개인정보 보호 및 보안 → 마이크 / 카메라**에서 터미널(또는 VS Code)을 허용해야 합니다.

---

## 실행

터미널 두 개를 사용합니다.

**터미널 1: 시뮬레이터 (계속 켜 둠)**

```bash
cd ~/reachi
source .venv/bin/activate
reachy-mini-daemon --sim
```

MuJoCo 창에 로봇이 보이면 성공입니다.

**터미널 2: 안테나 테스트**

```bash
cd ~/reachi
source .venv/bin/activate
python test_antenna.py
```

시뮬레이터의 안테나가 좌우로 움직이고 `Done!`이 출력되면 환경 설정 완료입니다.

> 실행 중 나오는 `No Reachy Mini Audio … found`, `IK error: Collision detected`, `onnxruntime … Failed to detect devices` 메시지는 실제 로봇이 없거나 WSL이라서 나오는 경고로, 오류가 아닙니다.

---

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `uv pip install` 중 `pycairo` / `pygobject` 빌드 실패, `Unknown compiler(s)` | 컴파일러·개발 라이브러리 없음 | WSL 1단계 패키지 설치 (맥: `xcode-select --install` + brew 패키지) |
| `ValueError: Namespace Gst not available` | GStreamer 없음 | WSL 1단계의 `gir1.2-gst*`, `gstreamer1.0-*` 설치 (맥: `brew install gstreamer`) |
| 시뮬레이터가 심하게 느리고 CPU 사용률이 매우 높음 (WSL) | CPU 소프트웨어 렌더링 | WSL 4단계 GPU 렌더링 설정, Windows NVIDIA 드라이버 최신화 |
| MuJoCo 창이 안 뜸 (WSL) | OpenGL/GLFW 라이브러리 | `sudo apt install -y libglfw3 mesa-utils` |
| VS Code에서 인터프리터를 못 찾음 (WSL) | VS Code가 WSL에 연결되지 않음 | WSL 5단계 참고, 경로 직접 입력 |
| `apt` 실행 시 `Could not get lock` | Ubuntu 자동 업데이트 진행 중 | 끝날 때까지 기다리기 (잠금 파일 삭제 금지) |
| `test_antenna.py` 연결 실패 | 데몬이 꺼져 있거나 아직 시작 중 | 터미널 1의 데몬 확인 후 다시 실행 |

## 폴더 구조

```
reachi/
├── README.md
├── requirements.txt     # Python 패키지 목록
├── test.py              # Python 실행 확인용
└── test_antenna.py      # Reachy Mini 안테나 동작 테스트
```
