"""
지퍼단추Agent 런처 — CMD 창 없이 백엔드 + 프론트 실행
더블클릭 또는 ZipperButtonAgent.exe 로 실행.

구조:
  backend/  — FastAPI uvicorn (127.0.0.1:8003)
  frontend/dist/ — 빌드된 정적 파일 (python -m http.server 5175)
  logs/     — 런타임 로그 저장

DEMO_MODE=1 인 경우 backend/.env 기준으로 지퍼/단추 7월 시연 데이터 자동 seed.
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

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent

BACKEND_DIR = BASE / "backend"
FRONTEND_DIST = BASE / "frontend" / "dist"
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
        _log(".env 없음 → .env.demo 복사 (DEMO_MODE=1, 첫 실행 시연 데이터 준비)")
    else:
        _log("[경고] .env / .env.demo 모두 없음 - 백엔드 DB 설정 누락 가능")


def _find_python() -> str:
    for cmd in ["py", "python", "python3"]:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
            if r.returncode == 0:
                return cmd
        except Exception:
            pass
    return "python"


def _start_backend(py: str) -> tuple:
    log_file = open(LOGS_DIR / "backend.log", "a", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env["DEMO_MODE"] = "1"
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1",
         "--port", "8003"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log_file,
        stderr=log_file,
        creationflags=CREATE_NO_WINDOW,
    )
    return proc, log_file


def _start_frontend(py: str) -> tuple:
    log_file = open(LOGS_DIR / "frontend.log", "a", encoding="utf-8", buffering=1)

    if FRONTEND_DIST.exists():
        _log(f"프론트: dist 정적 서빙 — {FRONTEND_DIST}")
        proc = subprocess.Popen(
            [py, "-m", "http.server", "5175",
             "--directory", str(FRONTEND_DIST)],
            stdout=log_file,
            stderr=log_file,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        _log("프론트: dist 없음 — npm run dev 대체 사용")
        proc = subprocess.Popen(
            "npm run dev",
            cwd=str(FRONTEND_DIR),
            stdout=log_file,
            stderr=log_file,
            shell=True,
            creationflags=CREATE_NO_WINDOW,
        )
    return proc, log_file


def _wait_backend(timeout: int = 30) -> bool:
    for _ in range(timeout):
        try:
            urllib.request.urlopen("http://127.0.0.1:8003/", timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    _log("=" * 50)
    _log("지퍼단추Agent 런처 시작")
    _log(f"BASE={BASE}")

    py = _find_python()
    _log(f"Python: {py}")

    _ensure_env()

    back_proc, back_log = _start_backend(py)
    _log(f"백엔드 PID={back_proc.pid} (포트 8003)")

    front_proc, front_log = _start_frontend(py)
    _log(f"프론트 PID={front_proc.pid} (포트 5175)")

    _log("백엔드 준비 대기 중...")
    ready = _wait_backend(30)
    if ready:
        _log("백엔드 준비 완료")
    else:
        _log("경고: 준비 대기 시간 초과 — 브라우저 열기 강행")

    webbrowser.open("http://localhost:5175")
    _log("브라우저 열기 완료 → http://localhost:5175")

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
        _log("지퍼단추Agent 런처 종료")


if __name__ == "__main__":
    main()
