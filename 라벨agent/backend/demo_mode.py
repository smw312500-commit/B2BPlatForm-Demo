import os


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def seed_demo_mode_if_enabled() -> None:
    if not demo_mode_enabled():
        return

    print("[DEMO_MODE] 라벨agent 기본/7월 시연 데이터 확인")
    try:
        from init_db import seed as seed_base

        seed_base()
    except Exception as exc:
        print(f"[DEMO_MODE] 라벨 기본 데이터 시드 실패: {exc}")

    try:
        from seed_july_demo import main as seed_july_demo

        seed_july_demo()
    except Exception as exc:
        print(f"[DEMO_MODE] 라벨 7월 데모 데이터 시드 실패: {exc}")
