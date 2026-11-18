"""Local account authentication for isolated workspaces."""

import base64
import os
from datetime import datetime, timezone

from argon2 import PasswordHasher, exceptions, low_level

from database import store


_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def _check_password(password):
    if not 12 <= len(password) <= 1024:
        raise ValueError("A senha deve ter de 12 a 1.024 caracteres.")


def _vault_key(password, salt_b64):
    return low_level.hash_secret_raw(password.encode("utf-8"), base64.b64decode(salt_b64),
                                     time_cost=2, memory_cost=19456, parallelism=1,
                                     hash_len=32, type=low_level.Type.ID)


def create_account(username, password, role="user", actor=None):
    _check_password(password)
    if role == "owner":
        if store.identity_user_count():
            raise ValueError("Proprietário já configurado.")
    elif not actor or actor.get("role") != "owner":
        raise PermissionError("Só o proprietário pode criar usuários.")
    salt = base64.b64encode(os.urandom(16)).decode("ascii")
    user_id = store.create_identity_user(username, _hasher.hash(password), salt, role)
    return {"id": user_id, "username": username.strip(), "role": role,
            "vault_key": _vault_key(password, salt)}


def login(username, password):
    user = store.get_identity_user(username=username.strip())
    if not user:
        raise ValueError("Usuário ou senha inválidos.")
    if user["locked_until"]:
        lock = datetime.fromisoformat(user["locked_until"]).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < lock:
            raise ValueError("Acesso temporariamente bloqueado. Tente novamente em alguns minutos.")
    try:
        valid = _hasher.verify(user["password_hash"], password)
    except (exceptions.VerifyMismatchError, exceptions.VerificationError):
        valid = False
    store.record_login_attempt(user["id"], valid)
    if not valid:
        raise ValueError("Usuário ou senha inválidos.")
    return {"id": user["id"], "username": user["username"], "role": user["role"],
            "vault_key": _vault_key(password, user["vault_salt"])}
