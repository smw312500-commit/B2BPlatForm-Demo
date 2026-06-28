# B2B Platform Demo

의류 B2B 공급망을 예시로 만든 AI agent 오케스트레이션 데모입니다.

생산사 agent가 자기 회사 데이터를 판단해 플랫폼에 보고하고, 플랫폼 agent가 보고를 취합해 배차, 보고 채널, 인사이트 화면으로 보여주는 구조입니다.

## 먼저 알아둘 점

이 데모는 완전 무설치 EXE가 아닙니다. 각 `*.exe`는 CMD 창을 숨겨서 실행해주는 런처이고, 내부적으로 로컬 Python과 `uvicorn`을 사용합니다.

현재 데모 DB는 MySQL이 아니라 각 agent의 `backend/demo.db` SQLite 파일을 사용합니다. 따라서 MySQL 설치는 필요 없습니다.

## 구성

- `플랫폼agent`: 전체 오케스트레이터, 대시보드, 보고 채널, 배차, AI 인사이트
- `라벨agent`: 라벨 생산사 agent
- `옷감agent`: 옷감 생산사 agent
- `지퍼단추agent`: 지퍼/단추 생산사 agent
- `물류agent`: 기사/차량/배차 상태를 다루는 물류사 agent
- `demo_data/four_year_supply_chain`: 4년치 가짜 공급망 데이터

## 실행 환경

- Windows 기준
- Python 3.10 이상 권장
- `pip` 사용 가능해야 함
- Node.js는 기본 실행에는 필요하지 않음
- MySQL은 필요하지 않음

Python 명령어는 PC마다 다를 수 있습니다. 아래 예시에서 `py`가 안 되면 `python`으로 바꿔서 실행하면 됩니다.

## 처음 실행 전 패키지 설치

PowerShell 또는 CMD에서 데모 폴더로 이동한 뒤 아래 명령을 한 번 실행합니다.

```powershell
py -m pip install --upgrade pip
py -m pip install -r ".\플랫폼agent\backend\requirements.txt"
py -m pip install -r ".\라벨agent\backend\requirements.txt"
py -m pip install -r ".\옷감agent\backend\requirements.txt"
py -m pip install -r ".\지퍼단추agent\backend\requirements.txt"
py -m pip install -r ".\물류agent\backend\requirements.txt"
```

## 실행 순서

아래 순서로 EXE를 더블클릭합니다.

1. `플랫폼agent/PlatformAgent.exe`
2. `물류agent/LogisticsAgent.exe`
3. `라벨agent/LabelAgent.exe`
4. `옷감agent/FabricAgent.exe`
5. `지퍼단추agent/ZipperButtonAgent.exe`

Windows 보안 경고가 뜨면 `추가 정보`를 누른 뒤 `실행`을 선택합니다.

## 접속 주소

- 플랫폼: `http://localhost:8000`
- 라벨사: `http://localhost:8001`
- 옷감사: `http://localhost:3000`
- 지퍼/단추사: `http://localhost:5175`
- 물류사: `http://localhost:3001`

브라우저가 자동으로 열리지 않으면 위 주소를 직접 입력하면 됩니다.

## 데모에서 확인할 흐름

- 각 생산사 agent는 자기 DB 기준으로 재고, 생산, 출고 상황을 판단합니다.
- 생산사 agent는 원본 DB 전체를 플랫폼에 넘기는 것이 아니라 판단된 보고를 플랫폼에 보냅니다.
- 플랫폼은 보고 채널에서 회사별 보고를 받고 저장합니다.
- 플랫폼은 물류 상태와 생산사 출고 보고를 조합해 배차/귀로 가능성을 판단합니다.
- AI 인사이트 화면은 4년치 데모 데이터를 바탕으로 자재 지연, 생산 납기 압박, 공급사 변경 후보 같은 판단 근거를 보여줍니다.

## 데이터 초기화

데모 데이터를 처음부터 다시 보고 싶으면 실행 중인 EXE를 모두 종료한 뒤 각 agent의 SQLite DB를 삭제하고 다시 실행합니다.

삭제 대상:

```text
플랫폼agent/backend/demo.db
라벨agent/backend/demo.db
옷감agent/backend/demo.db
지퍼단추agent/backend/demo.db
물류agent/backend/demo.db
```

다시 실행하면 demo seed 데이터가 자동으로 생성됩니다.

## 문제 해결

- `ModuleNotFoundError: uvicorn`이 나오면 패키지 설치 명령을 다시 실행합니다.
- 포트 충돌이 나면 기존에 켜져 있는 agent 또는 Python 프로세스를 종료한 뒤 다시 실행합니다.
- 화면이 안 뜨면 각 agent의 `logs/backend.log`, `logs/frontend.log`, `logs/launcher.log`를 확인합니다.
- GitHub ZIP으로 받았는데 EXE가 없다면 릴리즈 파일이 누락된 상태입니다. 데모 repo에는 `PlatformAgent.exe`, `LogisticsAgent.exe`, `FabricAgent.exe`, `LabelAgent.exe`, `ZipperButtonAgent.exe`가 포함되어 있어야 합니다.

## 보안

이 데모 repo에는 실제 API 키를 넣지 않습니다. OpenAI API를 연결하고 싶으면 각 agent의 `backend/.env`에 직접 `OPENAI_API_KEY`를 넣어서 로컬에서만 사용합니다.
