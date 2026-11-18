"""Per-user encrypted API credentials, outside every SQLite database."""

import base64
import json
import os
import re
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from database import store


VAULT_DIR = store.DB_PATH.parent / "vault"
ALLOWED = frozenset({
    "TRADING_LAB_LLM_BASE_URL", "TRADING_LAB_LLM_MODEL", "TRADING_LAB_LLM_API_KEY",
    "ALPACA_API_KEY", "ALPACA_API_SECRET",
    "BINANCE_SPOT_TESTNET_API_KEY", "BINANCE_SPOT_TESTNET_API_SECRET",
})


def _path(user_id):
    if not re.fullmatch(r"[0-9a-f]{32}", user_id):
        raise ValueError("Identificador de usuário inválido.")
    return VAULT_DIR / f"{user_id}.json"


def read_credentials(user_id, key):
    path = _path(user_id)
    if not path.exists():
        return {}
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        plaintext = AESGCM(key).decrypt(base64.b64decode(envelope["nonce"]),
                                        base64.b64decode(envelope["ciphertext"]),
                                        user_id.encode("ascii"))
        data = json.loads(plaintext)
        if not isinstance(data, dict) or not set(data).issubset(ALLOWED):
            raise ValueError()
        return data
    except (InvalidTag, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Cofre de credenciais indisponível para esta sessão.") from None


def save_credentials(user_id, key, changes):
    if not set(changes).issubset(ALLOWED):
        raise ValueError("Campo de credencial desconhecido.")
    data = read_credentials(user_id, key)
    for name, value in changes.items():
        if not isinstance(value, str):
            raise ValueError("Valor de credencial inválido.")
        if value:
            data[name] = value.strip()
        else:
            data.pop(name, None)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(data, sort_keys=True).encode("utf-8"),
                                     user_id.encode("ascii"))
    envelope = {"version": 1, "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(ciphertext).decode("ascii")}
    path = _path(user_id)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(envelope), encoding="utf-8")
    os.replace(temp_path, path)
    return {name: bool(data.get(name)) for name in ALLOWED}
