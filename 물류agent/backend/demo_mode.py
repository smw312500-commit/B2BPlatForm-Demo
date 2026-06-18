import os


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def seed_demo_mode_if_enabled() -> None:
    if not demo_mode_enabled():
        return

    print("[DEMO_MODE] 물류agent 기사/차량 시연 데이터 확인")
    try:
        from init_db import seed as seed_base

        seed_base()
    except Exception as exc:
        print(f"[DEMO_MODE] 물류 데모 데이터 시드 실패: {exc}")
