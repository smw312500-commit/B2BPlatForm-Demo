"""
옷감Agent 런처 — CMD 창 없이 백엔드 + 프론트 실행
더블클릭 또는 FabricAgent.exe 로 실행.

구조:
  backend/  — FastAPI uvicorn (127.0.0.1:8002), backend/venv 우선 사용
  frontend/build/ — CRA 빌드 정적 파일 (python -m http.server 3000)
  logs/     — 런타임 로그 저장

DEMO_MODE=1 로 백엔드를 실행해 첫 기동 시 7월 원단 시연 데이터를 자동 seed 한다
(demo_mode.seed_demo_mode_if_enabled → seed_july_demo, 이미 7월 데이터가 있으면 건너뜀).
플랫폼 미기동이어도 platform_retry 가 보고를 재전송한다.
"""
import datetime
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000  # Windows: CMD 창 숨김
BACKEND_PORT = 8002
FRONTEND_PORT = 3000

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent

BACKEND_DIR = BASE / "backend"
FRONTEND_BUILD = BASE / "frontend" / "build"
FRONTEND_DIR = BASE / "frontend"
LOGS_DIR = BASE / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    line = f"[{_ts()}] {msg}\n"
    try:
        with open(LOGS_DIR / "launcher.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _ensure_env() -> None:
    """backend/.env 가 없으면 비밀값 없는 .env.demo 를 복사 (데모 첫 실행 대비).
    기존 .env 가 있으면 절대 덮어쓰지 않는다(개발 PC 설정 보존)."""
    env_path = BACKEND_DIR / ".env"
    demo_path = BACKEND_DIR / ".env.demo"
    if env_path.exists():
        _log(".env 확인됨 (기존 설정 유지)")
        return
    if demo_path.exists():
        shutil.copyfile(demo_path, env_path)
        _log(".env 없음 → .env.demo 복사 (DEMO_MODE=1, 첫 실행 7월 시연 데이터 준비)")
    else:
        _log("[경고] .env / .env.demo 모두 없음 - 백엔드 DB 설정 누락 가능")


def _find_python() -> str:
    """백엔드 실행용 파이썬: backend/venv 우선, 없으면 시스템 파이썬."""
    venv_py = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    for cmd in ["py", "python", "python3"]:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
            if r.returncode == 0:
                return cmd
        except Exception:
            pass
    return "python"


def _start_backend(py: str) -> tuple[subprocess.Popen, object]:
    log_file = open(LOGS_DIR / "backend.log", "a", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env["DEMO_MODE"] = "1"  # EXE 실행 시 항상 7월 시연 데이터 자동 준비 (dotenv 보다 우선)
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1",
         "--port", str(BACKEND_PORT)],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log_file,
        stderr=log_file,
        creationflags=CREATE_NO_WINDOW,
    )
    return proc, log_file


def _start_frontend(py: str) -> tuple[subprocess.Popen, object]:
    log_file = open(LOGS_DIR / "frontend.log", "a", encoding="utf-8", buffering=1)

    if FRONTEND_BUILD.exists():
        _log(f"프론트: build 정적 서빙 — {FRONTEND_BUILD}")
        proc = subprocess.Popen(
            [py, "-m", "http.server", str(FRONTEND_PORT),
             "--bind", "127.0.0.1",
             "--directory", str(FRONTEND_BUILD)],
            stdout=log_file,
            stderr=log_file,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        _log("프론트: build 없음 — npm start 대체 사용")
        env = os.environ.copy()
        env["BROWSER"] = "none"
        proc = subprocess.Popen(
            "npm start",
            cwd=str(FRONTEND_DIR),
            env=env,
            stdout=log_file,
            stderr=log_file,
            shell=True,
            creationflags=CREATE_NO_WINDOW,
        )
    return proc, log_file


def _wait_backend(timeout: int = 40) -> bool:
    url = f"http://127.0.0.1:{BACKEND_PORT}/health"
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    _log("=" * 50)
    _log("옷감Agent 런처 시작")
    _log(f"BASE={BASE}")

    py = _find_python()
    _log(f"Python: {py}")

    _ensure_env()

    back_proc, back_log = _start_backend(py)
    _log(f"백엔드 PID={back_proc.pid} (포트 {BACKEND_PORT})")

    front_proc, front_log = _start_frontend(py)
    _log(f"프론트 PID={front_proc.pid} (포트 {FRONTEND_PORT})")

    _log("백엔드 준비 대기 중...")
    ready = _wait_backend(40)
    _log("백엔드 준비 완료" if ready else "경고: 준비 대기 시간 초과 — 브라우저 열기 강행")

    webbrowser.open(f"http://localhost:{FRONTEND_PORT}")
    _log(f"브라우저 열기 완료 → http://localhost:{FRONTEND_PORT}")

    try:
        back_proc.wait()
    except KeyboardInterrupt:
        _log("KeyboardInterrupt — 종료 처리")
    finally:
        _log("프로세스 종료 중...")
        for proc in (back_proc, front_proc):
            try:
                proc.terminate()
            except Exception:
                pass
        for f in (back_log, front_log):
            try:
                f.close()
            except Exception:
                pass
        _log("옷감Agent 런처 종료")


if __name__ == "__main__":
    main()
