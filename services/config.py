"""Load local environment settings without overriding process variables."""

from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
import os

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
_user_credentials = ContextVar("user_credentials", default=None)


def load_local_env():
    """Read the project .env if present; keep explicitly set environment values."""
    return load_dotenv(dotenv_path=ROOT / ".env", override=False)


@contextmanager
def credential_context(credentials):
    """In a signed-in workspace, never fall back to process-wide API keys."""
    token = _user_credentials.set(dict(credentials))
    try:
        yield
    finally:
        _user_credentials.reset(token)


def current_credentials():
    selected = _user_credentials.get()
    return os.environ if selected is None else selected
