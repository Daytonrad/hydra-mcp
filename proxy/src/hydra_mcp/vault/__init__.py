"""Token vault: AES-256-GCM encryption of upstream tokens and OAuth client secrets.

Version 1 (this file): one master key in `data_dir/vault.key` (mode 0600), separate from the
SQLite database, so a copy of the database alone decrypts nothing. Each ciphertext is bound to
its row through the AEAD associated data (e.g. "token:gmail-work"), so a blob copied onto
another account's row fails to decrypt.

Planned (design doc, "client-keyed vault"): one key per account, wrapped only into the key
slots of the client logins granted that account, so a client can never decrypt an account it
was not granted, even through a proxy bug.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
VERSION = b"\x01"


class VaultError(RuntimeError):
    pass


class Vault:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise VaultError("vault key must be 32 bytes")
        self._aead = AESGCM(key)

    @classmethod
    def from_dir(cls, data_dir: Path) -> Vault:
        data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = data_dir / "vault.key"
        if path.exists():
            key = path.read_bytes()
        else:
            key = secrets.token_bytes(32)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
        return cls(key)

    def seal(self, data: dict, *, aad: str) -> bytes:
        nonce = secrets.token_bytes(NONCE_BYTES)
        ct = self._aead.encrypt(nonce, json.dumps(data).encode(), aad.encode())
        return VERSION + nonce + ct

    def open(self, blob: bytes, *, aad: str) -> dict:
        if not blob or blob[:1] != VERSION:
            raise VaultError("unknown vault blob version")
        nonce, ct = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
        try:
            return json.loads(self._aead.decrypt(nonce, ct, aad.encode()))
        except Exception as exc:  # InvalidTag, JSON errors
            raise VaultError("cannot decrypt vault blob") from exc
