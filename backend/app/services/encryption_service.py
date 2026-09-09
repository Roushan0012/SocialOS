"""SocialOS Token Encryption Service (AES-256-GCM).

Provides authenticated encryption and decryption for sensitive OAuth tokens at rest.
Ensures zero-leakage of raw tokens, credentials, or keys in logs, errors, or API responses.
"""
import base64
import hashlib
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class TokenDecryptionError(Exception):
    """Raised when token decryption or authentication tag verification fails."""
    pass


class TokenEncryptionService:
    """AES-256-GCM token encryption service with authenticated tag verification."""

    VERSION_PREFIX = "v1"

    def __init__(self, key: Optional[str] = None) -> None:
        raw_key = key or settings.SOCIAL_TOKEN_ENCRYPTION_KEY
        if not raw_key:
            raise ValueError("SOCIAL_TOKEN_ENCRYPTION_KEY is not configured.")
        self._key_bytes = self._derive_key(raw_key)
        self._aesgcm = AESGCM(self._key_bytes)

    @staticmethod
    def _derive_key(key_str: str) -> bytes:
        """Derive a 32-byte (256-bit) AES key from the configured key string.
        
        Supports:
        - 64-character hex string (32 raw bytes)
        - 44-character base64/urlsafe-base64 string (32 raw bytes)
        - Arbitrary strong passphrase via SHA-256 digest
        """
        key_str = key_str.strip()
        if len(key_str) == 64:
            try:
                return bytes.fromhex(key_str)
            except ValueError:
                pass

        if len(key_str) == 44:
            try:
                decoded = base64.urlsafe_b64decode(key_str + "==")
                if len(decoded) == 32:
                    return decoded
            except Exception:
                pass

        # Fallback to SHA-256 key derivation
        return hashlib.sha256(key_str.encode("utf-8")).digest()

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Encrypt plaintext using AES-256-GCM with a fresh 12-byte random nonce.
        
        Output format: 'v1:<base64url(nonce + ciphertext_and_tag)>'
        Returns None if plaintext is None or empty.
        """
        if plaintext is None:
            return None
        if not plaintext:
            return ""

        nonce = os.urandom(12)
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext_and_tag = self._aesgcm.encrypt(nonce, plaintext_bytes, None)

        payload = nonce + ciphertext_and_tag
        encoded = base64.urlsafe_b64encode(payload).decode("ascii")
        return f"{self.VERSION_PREFIX}:{encoded}"

    def decrypt(self, encrypted_value: Optional[str]) -> Optional[str]:
        """Decrypt an AES-256-GCM encrypted payload and verify authenticity.
        
        Raises TokenDecryptionError if the ciphertext is tampered, corrupted,
        or encrypted with an invalid key. Never leaks plaintext in exceptions.
        """
        if encrypted_value is None:
            return None
        if not encrypted_value:
            return ""

        try:
            if not encrypted_value.startswith(f"{self.VERSION_PREFIX}:"):
                raise TokenDecryptionError("Invalid encrypted token format or unsupported version.")

            _, encoded_payload = encrypted_value.split(":", 1)
            raw_data = base64.urlsafe_b64decode(encoded_payload.encode("ascii"))

            if len(raw_data) < 12 + 16:  # 12-byte nonce + minimum 16-byte auth tag
                raise TokenDecryptionError("Ciphertext payload is truncated or invalid.")

            nonce = raw_data[:12]
            ciphertext_and_tag = raw_data[12:]

            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext_and_tag, None)
            return decrypted_bytes.decode("utf-8")
        except TokenDecryptionError:
            raise
        except Exception as exc:
            # Mask internal cryptographic errors to prevent information leakage
            raise TokenDecryptionError("Decryption failed: authenticity check failed or corrupted data.") from None


_default_service: Optional[TokenEncryptionService] = None


def get_encryption_service() -> TokenEncryptionService:
    """Get or instantiate the singleton TokenEncryptionService."""
    global _default_service
    if _default_service is None:
        _default_service = TokenEncryptionService()
    return _default_service


def encrypt_token(token: Optional[str]) -> Optional[str]:
    """Convenience wrapper to encrypt a token string."""
    return get_encryption_service().encrypt(token)


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Convenience wrapper to decrypt an encrypted token string."""
    return get_encryption_service().decrypt(encrypted_token)
