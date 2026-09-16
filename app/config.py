import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

NANSEN_API_KEY = os.getenv("NANSEN_API_KEY", "").strip()

_env_demo = os.getenv("DEMO_MODE", "").strip().lower()
if _env_demo in ("1", "true", "yes"):
    DEMO_MODE = True
elif _env_demo in ("0", "false", "no"):
    DEMO_MODE = False
else:
    DEMO_MODE = not NANSEN_API_KEY


def _int_env(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, "").strip())
        return v if v > 0 else default
    except ValueError:
        return default


POLL_POSITIONS_SEC = _int_env("POLL_POSITIONS_SEC", 180)
POLL_TRADES_SEC = _int_env("POLL_TRADES_SEC", 180)
POLL_SMART_SEC = _int_env("POLL_SMART_SEC", 300)
POLL_LEADERBOARD_SEC = _int_env("POLL_LEADERBOARD_SEC", 1800)
AUTO_PAUSE_CALLS = _int_env("AUTO_PAUSE_CALLS", 0)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "").strip()
