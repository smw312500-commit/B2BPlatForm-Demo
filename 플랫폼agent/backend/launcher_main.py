"""
EXE 실행 전용 진입점.
main.py의 FastAPI app을 그대로 import 한 뒤,
frontend/dist/ 가 있으면 정적 파일을 마운트해 포트 8000 하나로 모든 것을 서빙한다.

사용법 (launcher.py / build_exe.bat 에서 호출):
  uvicorn launcher_main:app --host 127.0.0.1 --port 8000
"""
from pathlib import Path

from main import app  # noqa: F401 — API 라우터 포함한 FastAPI 앱 로드

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _DIST.exists():
    try:
        from fastapi.staticfiles import StaticFiles

        # GET "/" 헬스체크 라우트가 StaticFiles 보다 우선하므로 제거
        app.routes[:] = [
            r for r in app.routes
            if not (
                getattr(r, "path", None) == "/"
                and "GET" in getattr(r, "methods", set())
            )
        ]

        app.mount(
            "/",
            StaticFiles(directory=str(_DIST), html=True),
            name="spa",
        )
    except Exception as exc:
        print(f"[launcher_main] StaticFiles 마운트 실패 (계속 진행): {exc}")
