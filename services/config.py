"""Load local environment settings without overriding process variables."""

from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def load_local_env():
    """Read the project .env if present; keep explicitly set environment values."""
    return load_dotenv(dotenv_path=ROOT / ".env", override=False)
