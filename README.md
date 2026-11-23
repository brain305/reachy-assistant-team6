# Reachy Mini 개인 비서 (딥러닝 6조)

Reachy Mini 시뮬레이터(MuJoCo) 위에서 동작하는 음성 대화형 개인 비서 프로젝트입니다.

- **기본 기능:** 음성 대화, 대화 내용에 따른 감정 표현(안테나·고개·몸통), 시각 정보 인식
- **추가 기능:** IT 영어 기사 요약, 감정 공감 및 일기 작성, 일정 관리, 학습 보조

현재 저장소에는 **기본 개발 환경 설정**과 **음성 대화 파이프라인**(STT → LLM → TTS + 감정 모션)이 들어 있습니다.
각 기능은 이 공통 모듈(`stt`, `llm`, `tts`, `motion`)을 가져다 쓰면 됩니다. → [공통 모듈 사용법](#공통-모듈-사용법)

## 요구 사항

| 항목            | 버전                                               |
| --------------- | -------------------------------------------------- |
| Python          | 3.12                                               |
| 패키지 관리     | [uv](https://docs.astral.sh/uv/)                   |
| Reachy Mini SDK | `reachy-mini[mujoco]` 1.14.0 (`requirements.txt`)  |
| OS              | Windows + WSL2 (Ubuntu) 또는 macOS (Apple Silicon) |


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

| 패키지                                                                     | 필요한 이유                                              |
| -------------------------------------------------------------------------- | -------------------------------------------------------- |
| `build-essential`, `pkg-config`, `libcairo2-dev`, `libgirepository1.0-dev` | SDK가 쓰는 `pygobject`를 리눅스에서 직접 컴파일하기 위해 |
| `gir1.2-gst*`, `gstreamer1.0-*`                                            | 데몬이 카메라·오디오 처리에 쓰는 GStreamer               |

### 2. uv 설치 (없는 경우)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 저장소 클론 + 가상환경

```bash
cd ~
git clone <저장소 URL> reachy
cd reachy
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

| WSL                                       | macOS                                      |
| ----------------------------------------- | ------------------------------------------ |
| `build-essential`                         | Xcode Command Line Tools                   |
| `libcairo2-dev`, `libgirepository1.0-dev` | `brew install cairo gobject-introspection` |
| `gstreamer1.0-*`                          | `brew install gstreamer`                   |

### 2. 저장소 클론 + 가상환경 (WSL과 동일)

```bash
git clone <저장소 URL> reachy
cd reachy
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python -c "from reachy_mini import ReachyMini; print('Reachy Mini SDK OK')"
```

### 3. 시뮬레이터 실행 시 주의

macOS는 GUI 창을 메인 스레드에서만 띄울 수 있어서, MuJoCo 창이 뜨지 않으면 `mjpython`으로 실행해야 할 수 있습니다.

```bash
reachy-mini-daemon --sim                              # 실행 안됨
mjpython -m reachy_mini.daemon.app.main --sim         # 창이 안 뜨면 시도
```

위 코드 실행 전 마이크 권한이 없으면 실행 되지 않음
권한 허용 후 
```bash
mjpython -m reachy_mini.daemon.app.main --sim
```
코드 실행 바람

### 4. 권한

마이크·카메라를 쓸 때 **시스템 설정 → 개인정보 보호 및 보안 → 마이크 / 카메라**에서 터미널(또는 VS Code)을 허용 필요

---

## 실행

터미널 두 개를 사용합니다.

**터미널 1: 시뮬레이터 (계속 켜 둠)**

```bash
cd ~/reachy
source .venv/bin/activate
reachy-mini-daemon --sim
```

MuJoCo 창에 로봇이 보이면 성공입니다.

**터미널 2: 안테나 테스트**

```bash
cd ~/reachy
source .venv/bin/activate
python test_antenna.py
```

시뮬레이터의 안테나가 좌우로 움직이고 `Done!`이 출력되면 환경 설정 완료입니다.

> 실행 중 나오는 `No Reachy Mini Audio … found`, `IK error: Collision detected`, `onnxruntime … Failed to detect devices` 메시지는 실제 로봇이 없거나 WSL이라서 나오는 경고로, 오류가 아닙니다.

---

## 음성 대화 실행

### 1. API 키 설정 (`.env`)

[Google AI Studio](https://aistudio.google.com/apikey)에서 Gemini API 키를 발급받고, `.env.example`을 복사해 키를 넣습니다.

```bash
cp .env.example .env
# .env 를 열어 GEMINI_API_KEY= 뒤에 키 붙여넣기
```

> `.env`는 `.gitignore`에 들어 있어 커밋되지 않습니다. **키를 코드나 채팅에 올리지 마세요.**

| 변수             | 필수 | 기본값              | 설명                                           |
| ---------------- | ---- | ------------------- | ---------------------------------------------- |
| `GEMINI_API_KEY` | ✅   |                     | Gemini API 키                                  |
| `GEMINI_MODEL`   |      | `gemini-3.8-flash`  | 사용할 Gemini 모델                             |
| `STT_MODEL`      |      | `large-v3-turbo`    | Whisper 모델 (`small`로 바꾸면 빠르지만 덜 정확) |
| `STT_DEVICE`     |      | 자동                | `cpu` / `cuda` 강제 지정                       |
| `TTS_VOICE`      |      | `ko-KR-SunHiNeural` | `ko-KR-InJoonNeural`(남성) 등                  |
| `TTS_RATE`       |      | `+0%`               | 말 빠르기 (예: `+10%`)                         |

### 2. 실행

```bash
# 터미널 1: 시뮬레이터 (위 '실행' 참고. 꺼져 있으면 모션 없이 음성 대화만 동작)
# 터미널 2
source .venv/bin/activate
python voice_chat.py
```

말을 하면 자동으로 감지해서 인식하고, Reachy가 대답을 읽으며 감정 모션을 합니다. `Ctrl+C`로 종료합니다.

- **첫 실행 시** Whisper 모델(약 1.6GB)을 내려받아 오래 걸립니다.
- 마이크 권한이 필요합니다 (macOS: 위 '권한' 참고).
- `python`이 anaconda 등 다른 Python을 가리키면 `ModuleNotFoundError`가 납니다. 반드시 `.venv`를 활성화하세요 (`which python`으로 확인).

### 모듈별 테스트

| 명령                       | 확인하는 것                              |
| -------------------------- | ---------------------------------------- |
| `python test_stt.py`       | 마이크 → 텍스트 (파일 경로를 주면 파일 변환) |
| `python test_llm.py`       | 키보드 입력 → LLM 대답·감정 JSON         |
| `python test_antenna.py`   | 시뮬레이터 연결                          |

---

## 공통 모듈 사용법

```
마이크 → stt → llm.ReachyChat → { answer, emotion, intensity }
                                   ├→ tts.speak(answer)
                                   └→ motion.express(emotion, intensity)
```

### `llm` — Gemini

```python
from llm import ReachyChat, generate_text, search_web

# 대화 (기록 유지, 대답+감정 JSON). 날씨·뉴스처럼 최신 정보가 필요할 때만 자동으로 구글 검색
chat = ReachyChat()
reply = chat.send("오늘 서울 날씨 어때?")
reply.answer      # "오늘 서울은 흐리고 ..."  → TTS로 읽을 문장
reply.emotion     # Emotion.NEUTRAL 등 (happy / sad / curious / surprised / comforting / neutral)
reply.intensity   # 0.0 ~ 1.0
chat.last_search_query  # 검색했으면 검색어, 아니면 None

# 일반 텍스트 생성 (요약, 일기 정리 등)
generate_text("다음 기사를 3줄로 요약해줘: ...", system="너는 IT 기자야")

# 최신 정보 검색 (구글 검색 결과 3문장 요약)
search_web("이번 주 IT 뉴스")
```

### `stt` — 음성 → 텍스트 (로컬 Whisper)

```python
from stt import SpeechToText
stt = SpeechToText()
text = stt.listen()              # 말이 끝날 때까지 듣고 텍스트 반환 (말이 없으면 None)
text = stt.transcribe("a.wav")   # 파일 또는 16kHz float32 배열
```

말 시작·끝은 Silero VAD가 자동 감지합니다 (0.8초 조용하면 종료). `stt.listen(silence_ms=1200)`처럼 조절할 수 있습니다.

### `tts` — 텍스트 → 음성 (edge-tts, 인터넷 필요)

```python
from tts import TextToSpeech
tts = TextToSpeech()
tts.speak("안녕, 난 리치야")      # 다 읽을 때까지 기다림
tts.speak("잠깐 찾아볼게", wait=False)  # 재생만 시작하고 바로 다음 코드 실행
```

### `motion` — 감정 모션

```python
from reachy_mini import ReachyMini
from motion import EmotionMotion

with ReachyMini(media_backend="no_media") as mini:   # no_media: 마이크·스피커는 stt/tts가 사용
    motion = EmotionMotion(mini)
    motion.express("happy", 0.8)              # 백그라운드 실행 (말하면서 움직이기)
    motion.express("sad", 0.5, wait=True)     # 끝날 때까지 기다림
```

| emotion    | 동작                                                   |
| ---------- | ------------------------------------------------------ |
| happy      | 고개를 살짝 들고 안테나를 파닥이며 몸을 좌우로 들썩    |
| sad        | 천천히 고개를 숙이고 안테나를 축 늘어뜨림              |
| curious    | 고개 갸우뚱 + 한쪽 안테나만 쫑긋 (검색 중에도 사용)    |
| surprised  | 순간적으로 고개를 뒤로 젖히고 안테나를 앞으로 세움     |
| comforting | 안테나를 살짝 눕히고 천천히 두 번 끄덕                 |
| neutral    | 고개를 기울이며 두 번 끄덕 + 몸 살짝 회전              |

`intensity`에 따라 동작 크기가 0.5~1.0배로 바뀝니다. 각도는 `motion/__init__.py`에서 조절합니다.

### 알려진 문제

- **TTS 잡음:** edge-tts가 48kbps mp3로만 음성을 줘서 'ㅅ, ㅊ' 발음에서 지글거림이 있음 (고음역 필터로는 해결 안 됨). 엔진 교체 검토 중
- **응답 속도:** 일상 대화 약 5~10초, 검색이 필요한 질문은 15~20초 (검색 중에는 "잠깐 찾아볼게"를 먼저 말함)
- **WSL 미검증:** 음성 파이프라인은 macOS에서만 테스트함. WSL은 마이크·스피커(WSLg 오디오)와 CUDA 설정이 추가로 필요할 수 있음
- **Mac GPU(MPS) 사용 안 함:** faster-whisper의 MPS 백엔드가 `IndexError: vector`로 자주 실패해서 CPU 사용

---

## 문제 해결

| 증상                                                                         | 원인                            | 해결                                                                            |
| ---------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------- |
| `uv pip install` 중 `pycairo` / `pygobject` 빌드 실패, `Unknown compiler(s)` | 컴파일러·개발 라이브러리 없음   | WSL 1단계 패키지 설치 (맥: `xcode-select --install` + brew 패키지)              |
| `ValueError: Namespace Gst not available`                                    | GStreamer 없음                  | WSL 1단계의 `gir1.2-gst*`, `gstreamer1.0-*` 설치 (맥: `brew install gstreamer`) |
| 시뮬레이터가 심하게 느리고 CPU 사용률이 매우 높음 (WSL)                      | CPU 소프트웨어 렌더링           | WSL 4단계 GPU 렌더링 설정, Windows NVIDIA 드라이버 최신화                       |
| MuJoCo 창이 안 뜸 (WSL)                                                      | OpenGL/GLFW 라이브러리          | `sudo apt install -y libglfw3 mesa-utils`                                       |
| VS Code에서 인터프리터를 못 찾음 (WSL)                                       | VS Code가 WSL에 연결되지 않음   | WSL 5단계 참고, 경로 직접 입력                                                  |
| `apt` 실행 시 `Could not get lock`                                           | Ubuntu 자동 업데이트 진행 중    | 끝날 때까지 기다리기 (잠금 파일 삭제 금지)                                      |
| `test_antenna.py` 연결 실패                                                  | 데몬이 꺼져 있거나 아직 시작 중 | 터미널 1의 데몬 확인 후 다시 실행                                               |
| `ModuleNotFoundError: ctranslate2` 등                                        | `.venv`가 아닌 Python으로 실행  | `source .venv/bin/activate` 후 실행 (`which python`으로 확인)                   |
| `.env 에 GEMINI_API_KEY 가 없습니다`                                         | API 키 미설정                   | [음성 대화 실행 → 1. API 키 설정](#1-api-키-설정-env) 참고                      |
| `TypeError: open() got an unexpected keyword argument 'metadata_errors'`     | PyAV 19 설치됨                  | `uv pip install -r requirements.txt` (av 16.1.0으로 고정)                       |

## 폴더 구조

```
reachy/
├── README.md
├── requirements.txt     # Python 패키지 목록
├── .env.example         # .env 템플릿 (복사해서 API 키 입력)
├── voice_chat.py        # 음성 대화 전체 실행 (STT → LLM → TTS + 모션)
├── llm/                 # Gemini: 대화(ReachyChat), 텍스트 생성, 구글 검색
│   ├── __init__.py
│   ├── prompts.py       # 시스템 프롬프트 (말투, 감정 기준, 검색 기준)
│   └── schema.py        # LLM 응답 JSON 형식, 감정 목록
├── stt/                 # 로컬 Whisper STT + 음성 자동 감지(VAD)
│   ├── __init__.py
│   ├── recorder.py      # 마이크 녹음, 발화 구간 자르기
│   └── vad.py           # Silero VAD 실시간 버전
├── tts/                 # edge-tts 음성 출력
├── motion/              # 감정별 안테나·고개·몸통 동작
├── test_stt.py          # STT 테스트
├── test_llm.py          # LLM 테스트 (키보드 입력)
├── test.py              # Python 실행 확인용
└── test_antenna.py      # Reachy Mini 안테나 동작 테스트
```


---

## 2026-11: Skill 라우팅 / WSL 카메라 지원 (feature/vision-news 개선)

### 달라진 실행 구조

`voice_chat.py`는 STT 결과의 특정 단어를 조건문으로 비교하지 않습니다.
Gemini `skills/router.py`가 의도를 구조화된 JSON(`chat`, `vision`, `news`, `slack`)으로 판단하고,
`skills/runner.py`가 등록된 스킬을 실행합니다. 선택이 `chat`이면 기존 `ReachyChat`으로 보내
일반 음성 대화 및 감정 표현 기능을 유지합니다.

```text
STT → Gemini SkillRouter → chat  → ReachyChat → TTS + motion
                        → vision → webcam/image → Gemini vision → TTS + motion
                        → news   → RSS → Gemini summary → TTS + motion
                        → slack  → 최근 요약 → Slack Webhook → TTS + motion
```

- `카메라 관련 정보를 알려줘`는 카메라 촬영이 아닌 일반 대화로 분류하도록 지시되어 있습니다.
- `내가 들고 있는 물건이 뭐야?`는 실제 촬영을 요청하므로 vision에 해당합니다.
- `뉴스를 슬랙에 보내줘`는 기존 요약이 있을 때만 전송합니다.
- Skill 선택에는 Gemini API 호출이 추가되므로 응답 시간이 다소 늘어날 수 있습니다.
- LLM의 의도 선택은 확률적이므로 위 예시에서의 판단을 100% 보장하지 않습니다. 배포 전 실제 문장 테스트가 필요합니다.
- 스킬을 늘리려면 `skills/runner.py`에 함수를 등록하고 `skills/router.py`의 스키마·설명을 수정합니다.
- Slack 전송은 음성으로 명시적으로 요청한 경우에만 실행하도록 SkillRouter에 지시해 두었습니다.

### 기본 실행 (Windows / WSL)

가상환경과 필수 라이브러리를 설치하고 `.env.example`을 `.env`로 복사한 뒤
`GEMINI_API_KEY`에 유효한 키를 넣습니다. 뉴스 Slack 전송에는 `SLACK_WEBHOOK_URL`도 필요합니다.

```bash
# Linux / WSL
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python -m unittest test_skill_routing -v

# 터미널 1
reachy-mini-daemon --sim

# 터미널 2 (별도 터미널에서 가상환경 재활성화)
python voice_chat.py
```

기존 README의 WSL 시스템 라이브러리·마이크·스피커 설정도 선행되어야 합니다.

### 카메라: Windows 네이티브

기본값 `REACHY_CAMERA_SOURCE=auto`로 실행하면 Windows에서는 DirectShow 웹캠을 사용합니다.
Windows가 아닌 Linux에서는 V4L2 웹캠 장치를 시도합니다.

### 카메라: WSL에서 이미지 파일 사용 (가장 간단한 테스트)

WSL에 카메라 장치가 없더라도, 미리 촬영한 이미지를 이용해 이미지 인식 기능을 테스트할 수 있습니다.
WSL의 `.env`에 다음을 설정하세요.

```dotenv
REACHY_CAMERA_SOURCE=file
REACHY_CAMERA_IMAGE=/home/사용자이름/test_images/phone.jpg
```

Windows에 저장한 사진도 `/mnt/c/Users/사용자이름/Pictures/phone.jpg`처럼 접근할 수 있습니다.
이 모드에서는 매번 동일한 이미지를 사용하므로 실시간 웹캠 촬영은 하지 않습니다.

### 카메라: Windows 웹캠을 WSL에서 사용하기 (브리지)

WSL2의 일반적인 환경에서는 Windows 카메라가 리눅스 `/dev/video0`에 자동으로 나타나지 않습니다.
실시간 촬영을 위해 **Windows 측**에서 `windows_camera_bridge.py`를 실행하고, **WSL 측**에서
HTTP 이미지 요청을 보내는 방식을 추가했습니다.

1. Windows PowerShell에서 Python 3.12 및 `opencv-python`, `python-dotenv`를 준비합니다.
2. Windows 프로젝트의 `.env`에 아래를 설정합니다. 토큰은 충분히 긴 무작위 값으로 직접 만드세요.

   ```dotenv
   REACHY_CAMERA_BRIDGE_TOKEN=여기에_강력한_임의의_비밀문자열
   REACHY_CAMERA_BRIDGE_BIND=127.0.0.1
   REACHY_CAMERA_BRIDGE_PORT=8765
   ```

3. **Windows PowerShell**에서 실행:

   ```powershell
   python windows_camera_bridge.py
   ```

4. WSL의 `.env`에 다음을 설정합니다. Windows와 토큰 값이 같아야 합니다.

   ```dotenv
   REACHY_CAMERA_SOURCE=bridge
   REACHY_CAMERA_BRIDGE_URL=http://127.0.0.1:8765
   REACHY_CAMERA_BRIDGE_TOKEN=Windows와_동일한_비밀문자열
   ```

5. WSL에서 `python test_vision.py`로 확인한 뒤 `python voice_chat.py`를 실행합니다.

**WSL 네트워크 주의:** 위 localhost 주소는 mirrored networking을 사용하거나 Windows↔WSL localhost
연결이 가능한 구성에서 동작합니다. 기본 NAT 모드에서 WSL→Windows localhost 접근이 안 되면
Windows 호스트의 WSL에서 도달 가능한 IP를 `REACHY_CAMERA_BRIDGE_URL`에 적고,
Windows의 `REACHY_CAMERA_BRIDGE_BIND=0.0.0.0`으로 바꿔야 할 수 있습니다. 이 경우
Windows 방화벽에서 **신뢰할 수 있는 로컬 네트워크에서만** 포트 8765에 접근할 수 있도록 제한하세요.
토큰 헤더는 권한 확인용이지만 일반 HTTP 트래픽은 암호화되지 않으므로 공용망·인터넷에는 절대
노출하지 마세요. 네트워크 제약이나 방화벽 정책에 따라 브리지 접속이 불가능할 수 있습니다.

**중요:** 위 구성은 WSL에서도 이용할 수 있도록 코드를 준비한 것이며, 실제 팀원 WSL 장비의
웹캠/오디오/네트워크 연동을 검증한 것은 아닙니다. 실기기 테스트가 필요합니다.

### 테스트

```bash
python -m unittest test_skill_routing -v      # 오프라인 Skill 라우팅 + 실행기 테스트
python -m unittest test_skill_routing -v   # Skill 라우팅/실행기 단위 테스트(실제 API 불필요)
python test_vision.py                       # WSL에서는 file 또는 bridge 설정
python test_news.py
python test_slack.py                         # 실제 Slack에 메시지 전송됨
```

`test_slack.py`를 실행하면 실제로 Webhook의 지정 채널에 테스트 메시지가 전송됩니다.
`.env`는 `.gitignore`로 추적 제외하며, ZIP이나 PR에 비밀 키를 넣지 마세요.

### 코드 리뷰 반영 (1~8번)

- `news/__init__.py`: 뉴스 요약 프롬프트에서 마크다운/장식 기호 금지, TTS용 마크다운 제거. RSS 요청은 `requests.get(..., timeout=(5, 12))`로 수신 후 `feedparser.parse(response.content)`.
- `news/slack_sender.py`: Slack 전송은 Slack용 `*굵게*` 서식을 사용. 루트 `slack_sender.py`는 사용하지 않음.
- `requirements.txt`: 새 의존성 4개의 버전을 `==`로 고정.
- `voice_chat.py`: 감정·세기, STT/LLM 및 Skill 실행 시간 로그, `no_media` 주석 복구.
- `.env.example`: 원래 설명과 Slack/카메라 설정 안내 유지. 실제 API 키 및 Webhook URL은 `.env`에만 작성.
- `skills/runner.py`: Vision/News/Slack 코드는 해당 기능을 실행할 때만 import.
- `test_skill_routing.py`: 실행기/라우팅 단위 테스트 통합. `test_skill_router.py`는 삭제.
- 공통 `llm/` PR 기반 통합(리뷰 9번)은 **미적용**, 해당 PR 병합 후 처리 예정.

### 기존 브랜치에 수정본 덮어쓰기 시 주의

ZIP 압축 해제 후 파일을 덮어쓰는 것만으로는 **기존 파일이 삭제되지 않습니다.**
리뷰 2·8번을 반영하려면 프로젝트 폴더에서 아래 파일도 제거하세요 (PowerShell):

```powershell
Remove-Item .\slack_sender.py, .\test_skill_router.py -ErrorAction SilentlyContinue
```

삭제 전 `git status`로 기존 변경사항 확인을 권장합니다.

