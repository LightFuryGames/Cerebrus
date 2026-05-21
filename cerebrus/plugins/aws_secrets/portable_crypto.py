"""Encryption for portable AWS Secrets exports (.cbx, schema v3).

Format (binary, written verbatim to file):

    offset  size  field
    0       4     magic b"CBX3"
    4       1     version (=3)
    5       1     mode    (0 = embedded key, 1 = passphrase)
    6       16    salt_inner (random per-export, PBKDF2 salt for AES-GCM key)
    22      16    salt_outer (random per-export, PBKDF2 salt for Fernet key)
    38      12    nonce_inner (AES-GCM nonce)
    50      ..    fernet_token = Fernet(K_outer).encrypt(
                       aes_gcm_ciphertext || aes_gcm_tag
                   )

The plaintext is JSON. Two independent keys, two independent ciphers, two
independent salts -- compromising one layer alone does not yield secrets.

Embedded mode uses a constant pass embedded in the binary as the input to
PBKDF2; this is obfuscation, not security. Anyone with the Cerebrus binary
can derive K_outer/K_inner for embedded-mode files. Recipients without the
binary, or files using passphrase mode, are not affected.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"CBX3"
VERSION = 3
MODE_EMBEDDED = 0
MODE_PASSPHRASE = 1

PBKDF2_ITERS_INNER = 600_000
PBKDF2_ITERS_OUTER = 200_000
SALT_LEN = 16
NONCE_LEN = 12

# Obfuscated embedded passphrase. Reconstructed at runtime so a raw `strings`
# dump on the binary does not reveal the literal. Not security -- a determined
# attacker with the binary can derive this trivially.
_EMBEDDED_PARTS = (
    "Cerebrus",
    "Portable",
    "AWS",
    "Export",
    "2026",
    "v3",
    "shared",
    "team",
)
_EMBEDDED_SALT_PEPPER = b"\x9a\x4f\x21\xcd\x77\x10\x82\xee"


def _embedded_passphrase() -> bytes:
    joined = ".".join(_EMBEDDED_PARTS).encode("utf-8")
    return joined + _EMBEDDED_SALT_PEPPER


def _derive(passphrase: bytes, salt: bytes, iters: int, length: int = 32) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iters,
    )
    return kdf.derive(passphrase)


@dataclass
class EncryptedBundle:
    mode: int
    salt_inner: bytes
    salt_outer: bytes
    nonce_inner: bytes
    fernet_token: bytes

    def to_bytes(self) -> bytes:
        return (
            MAGIC
            + bytes([VERSION, self.mode])
            + self.salt_inner
            + self.salt_outer
            + self.nonce_inner
            + self.fernet_token
        )

    @classmethod
    def from_bytes(cls, blob: bytes) -> "EncryptedBundle":
        if len(blob) < 4 + 1 + 1 + SALT_LEN * 2 + NONCE_LEN:
            raise ValueError("Truncated CBX3 payload.")
        if blob[:4] != MAGIC:
            raise ValueError("Not a CBX3-encrypted export.")
        version = blob[4]
        if version != VERSION:
            raise ValueError(f"Unsupported CBX version: {version}")
        mode = blob[5]
        cursor = 6
        salt_inner = blob[cursor : cursor + SALT_LEN]
        cursor += SALT_LEN
        salt_outer = blob[cursor : cursor + SALT_LEN]
        cursor += SALT_LEN
        nonce_inner = blob[cursor : cursor + NONCE_LEN]
        cursor += NONCE_LEN
        fernet_token = blob[cursor:]
        return cls(
            mode=mode,
            salt_inner=salt_inner,
            salt_outer=salt_outer,
            nonce_inner=nonce_inner,
            fernet_token=fernet_token,
        )


def encrypt_payload(payload: dict, passphrase: str | None) -> bytes:
    """Encrypt a JSON-serialisable payload to a CBX3 binary blob."""
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    if passphrase:
        pass_bytes = passphrase.encode("utf-8")
        mode = MODE_PASSPHRASE
    else:
        pass_bytes = _embedded_passphrase()
        mode = MODE_EMBEDDED

    salt_inner = os.urandom(SALT_LEN)
    salt_outer = os.urandom(SALT_LEN)
    nonce_inner = os.urandom(NONCE_LEN)

    k_inner = _derive(pass_bytes, salt_inner, PBKDF2_ITERS_INNER)
    aesgcm = AESGCM(k_inner)
    inner_ct = aesgcm.encrypt(nonce_inner, plaintext, MAGIC)

    k_outer_raw = _derive(pass_bytes, salt_outer, PBKDF2_ITERS_OUTER)
    fernet_key = base64.urlsafe_b64encode(k_outer_raw)
    fernet = Fernet(fernet_key)
    fernet_token = fernet.encrypt(inner_ct)

    return EncryptedBundle(
        mode=mode,
        salt_inner=salt_inner,
        salt_outer=salt_outer,
        nonce_inner=nonce_inner,
        fernet_token=fernet_token,
    ).to_bytes()


class PassphraseRequired(Exception):
    """Raised when a passphrase-mode bundle is decrypted without one."""


class DecryptionFailed(Exception):
    """Raised when decryption fails (wrong passphrase, tampered file, etc.)."""


def decrypt_payload(blob: bytes, passphrase: str | None) -> dict:
    bundle = EncryptedBundle.from_bytes(blob)

    if bundle.mode == MODE_PASSPHRASE:
        if not passphrase:
            raise PassphraseRequired(
                "This export is passphrase-protected. Supply the passphrase."
            )
        pass_bytes = passphrase.encode("utf-8")
    elif bundle.mode == MODE_EMBEDDED:
        pass_bytes = (
            passphrase.encode("utf-8") if passphrase else _embedded_passphrase()
        )
    else:
        raise DecryptionFailed(f"Unknown CBX3 mode: {bundle.mode}")

    try:
        k_outer_raw = _derive(pass_bytes, bundle.salt_outer, PBKDF2_ITERS_OUTER)
        fernet_key = base64.urlsafe_b64encode(k_outer_raw)
        inner_ct = Fernet(fernet_key).decrypt(bundle.fernet_token)
    except InvalidToken as e:
        raise DecryptionFailed(
            "Outer cipher rejected the key (wrong passphrase or tampered file)."
        ) from e

    try:
        k_inner = _derive(pass_bytes, bundle.salt_inner, PBKDF2_ITERS_INNER)
        plaintext = AESGCM(k_inner).decrypt(bundle.nonce_inner, inner_ct, MAGIC)
    except Exception as e:
        raise DecryptionFailed(
            "Inner cipher rejected the key (wrong passphrase or tampered file)."
        ) from e

    try:
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise DecryptionFailed("Decrypted payload is not valid JSON.") from e


def looks_like_cbx3(blob: bytes) -> bool:
    return len(blob) >= 4 and blob[:4] == MAGIC
