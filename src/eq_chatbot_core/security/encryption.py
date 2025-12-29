"""
API key encryption using Fernet (AES-128-CBC).
"""

from __future__ import annotations


class FernetEncryption:
    """
    Fernet-based encryption for sensitive data like API keys.

    Fernet uses AES-128-CBC with HMAC-SHA256 for authentication.

    Usage:
        # Generate a new key
        key = FernetEncryption.generate_key()

        # Create encryption instance
        enc = FernetEncryption(key)

        # Encrypt/decrypt
        encrypted = enc.encrypt("my-api-key")
        decrypted = enc.decrypt(encrypted)
    """

    def __init__(self, key: str | bytes):
        """
        Initialize with an encryption key.

        Args:
            key: Fernet key (base64-encoded 32-byte key)
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError as e:
            raise ImportError(
                "cryptography package not installed. "
                "Install with: pip install cryptography"
            ) from e

        if isinstance(key, str):
            key = key.encode()

        self._fernet = Fernet(key)
        self._key = key

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new Fernet key.

        Returns:
            Base64-encoded key string (safe for storage)
        """
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()

    @classmethod
    def from_key(cls, key: str | bytes) -> "FernetEncryption":
        """
        Create instance from existing key.

        Args:
            key: Existing Fernet key

        Returns:
            FernetEncryption instance
        """
        return cls(key)

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt

        Returns:
            Encrypted bytes (Fernet token)
        """
        if not plaintext:
            return b""

        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes | str) -> str:
        """
        Decrypt an encrypted value.

        Args:
            ciphertext: Encrypted Fernet token

        Returns:
            Decrypted string

        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data)
        """
        if not ciphertext:
            return ""

        if isinstance(ciphertext, str):
            ciphertext = ciphertext.encode()

        return self._fernet.decrypt(ciphertext).decode()

    def encrypt_to_string(self, plaintext: str) -> str:
        """
        Encrypt and return as base64 string (for storage in text fields).

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        return self.encrypt(plaintext).decode()

    def decrypt_from_string(self, ciphertext: str) -> str:
        """
        Decrypt from base64 string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted string
        """
        return self.decrypt(ciphertext.encode())

    @property
    def key_fingerprint(self) -> str:
        """
        Get key fingerprint for debugging (first 8 chars of SHA256 hash).

        This is safe to log - it does NOT expose the actual key.
        """
        import hashlib

        return hashlib.sha256(self._key).hexdigest()[:8]
