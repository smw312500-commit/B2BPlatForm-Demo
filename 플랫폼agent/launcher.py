import datetime
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent

BACKEND_DIR = BASE / "backend"
LOGS_DIR = BASE / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    try:
        with open(LOGS_DIR / "launcher.log", "a", encoding="utf-8") as f:
            f.write(f"[{_ts()}] {msg}\n")
    except Exception:
        pass


def _ensure_env() -> None:
    env_path = BACKEND_DIR / ".env"
    demo_path = BACKEND_DIR / ".env.demo"
    if env_path.exists():
        _log("backend/.env exists; keeping current local settings")
        return
    if demo_path.exists():
        shutil.copyfile(demo_path, env_path)
        _log("backend/.env created from .env.demo")
    else:
        _log("warning: backend/.env.demo is missing")


def _find_uvicorn_cmd() -> list[str]:
    if shutil.which("uvicorn"):
        return ["uvicorn"]

    for python_cmd in ("py", "python", "python3"):
        try:
            result = subprocess.run([python_cmd, "-c", "import uvicorn"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return [python_cmd, "-m", "uvicorn"]
        except Exception:
            pass

    return ["py", "-m", "uvicorn"]


def _start_backend() -> tuple[subprocess.Popen, object]:
    uvicorn_cmd = _find_uvicorn_cmd()
    log_file = open(LOGS_DIR / "backend.log", "a", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env["DEMO_MODE"] = "1"
    proc = subprocess.Popen(
        uvicorn_cmd + ["launcher_main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log_file,
        stderr=log_file,
        creationflags=CREATE_NO_WINDOW,
    )
    return proc, log_file


def _wait_backend(timeout: int = 35) -> bool:
    for _ in range(timeout):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    _log("=" * 50)
    _log("PlatformAgent launcher started")
    _log(f"BASE={BASE}")
    _ensure_env()

    proc, log_file = _start_backend()
    _log(f"backend pid={proc.pid}, port=8000, demo_mode=1")

    if _wait_backend():
        _log("backend ready")
    else:
        _log("warning: backend readiness timeout")

    webbrowser.open("http://localhost:8000")

    try:
        proc.wait()
    except KeyboardInterrupt:
        _log("keyboard interrupt")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            log_file.close()
        except Exception:
            pass
        _log("PlatformAgent launcher stopped")


if __name__ == "__main__":
    main()
