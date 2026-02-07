"""
Unit tests for the FernetEncryption module.

Tests encryption/decryption roundtrips, key management, error handling,
Unicode support, and ImportError handling when cryptography is missing.
"""

import base64
import hashlib
import sys
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from eq_chatbot_core.security.encryption import FernetEncryption


# =============================================================================
# Key Generation Tests
# =============================================================================


@pytest.mark.unit
class TestKeyGeneration:
    """Test Fernet key generation."""

    def test_generate_key_returns_string(self):
        """Test that generate_key returns a string."""
        key = FernetEncryption.generate_key()

        assert isinstance(key, str)

    def test_generate_key_is_valid_base64(self):
        """Test that generated key is valid base64-encoded 32 bytes."""
        key = FernetEncryption.generate_key()

        raw = base64.urlsafe_b64decode(key)
        assert len(raw) == 32

    def test_generate_key_can_initialize_fernet(self):
        """Test that generated key can create a native Fernet instance."""
        key = FernetEncryption.generate_key()

        # Should not raise
        Fernet(key.encode())

    def test_generate_key_produces_unique_keys(self):
        """Test that successive calls produce different keys."""
        keys = {FernetEncryption.generate_key() for _ in range(50)}

        assert len(keys) == 50

    def test_generate_key_creates_working_instance(self):
        """Test that generated key can construct a FernetEncryption."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        assert enc is not None


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestInitialization:
    """Test FernetEncryption initialization with string vs bytes keys."""

    def test_init_with_string_key(self):
        """Test initialization with a string key."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        assert enc is not None

    def test_init_with_bytes_key(self):
        """Test initialization with a bytes key."""
        key = FernetEncryption.generate_key().encode()
        enc = FernetEncryption(key)

        assert enc is not None

    def test_init_stores_key_as_bytes(self):
        """Test that internal key is stored as bytes regardless of input type."""
        key_str = FernetEncryption.generate_key()
        enc = FernetEncryption(key_str)

        assert isinstance(enc._key, bytes)
        assert enc._key == key_str.encode()

    def test_init_bytes_key_stays_as_bytes(self):
        """Test that bytes key input stays as bytes internally."""
        key_bytes = FernetEncryption.generate_key().encode()
        enc = FernetEncryption(key_bytes)

        assert isinstance(enc._key, bytes)
        assert enc._key == key_bytes

    def test_init_with_invalid_key_raises_error(self):
        """Test that an invalid key raises an error."""
        with pytest.raises(Exception):
            FernetEncryption("not-a-valid-fernet-key")

    def test_init_with_empty_string_raises_error(self):
        """Test that an empty string key raises an error."""
        with pytest.raises(Exception):
            FernetEncryption("")

    def test_string_and_bytes_key_produce_same_encryption(self):
        """Test that string and bytes forms of the same key are interchangeable."""
        key_str = FernetEncryption.generate_key()
        key_bytes = key_str.encode()

        enc_str = FernetEncryption(key_str)
        enc_bytes = FernetEncryption(key_bytes)

        plaintext = "cross-init-test"
        encrypted = enc_str.encrypt(plaintext)

        # Bytes-initialized instance can decrypt string-initialized ciphertext
        assert enc_bytes.decrypt(encrypted) == plaintext


# =============================================================================
# from_key Factory Method Tests
# =============================================================================


@pytest.mark.unit
class TestFromKeyFactory:
    """Test the from_key class method factory."""

    def test_from_key_returns_instance(self):
        """Test that from_key returns a FernetEncryption instance."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption.from_key(key)

        assert isinstance(enc, FernetEncryption)

    def test_from_key_with_string(self):
        """Test from_key with string key produces working encryption."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption.from_key(key)
        plaintext = "test-api-key"

        encrypted = enc.encrypt(plaintext)
        assert enc.decrypt(encrypted) == plaintext

    def test_from_key_with_bytes(self):
        """Test from_key with bytes key produces working encryption."""
        key = FernetEncryption.generate_key().encode()
        enc = FernetEncryption.from_key(key)
        plaintext = "test-api-key"

        encrypted = enc.encrypt(plaintext)
        assert enc.decrypt(encrypted) == plaintext

    def test_from_key_equivalent_to_constructor(self):
        """Test that from_key produces same behavior as direct constructor."""
        key = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key)
        enc2 = FernetEncryption.from_key(key)

        plaintext = "identical-output-expected"
        encrypted1 = enc1.encrypt(plaintext)
        encrypted2 = enc2.encrypt(plaintext)

        # Both instances can decrypt each other's output
        assert enc2.decrypt(encrypted1) == plaintext
        assert enc1.decrypt(encrypted2) == plaintext


# =============================================================================
# Encrypt / Decrypt Roundtrip Tests
# =============================================================================


@pytest.mark.unit
class TestEncryptDecryptRoundtrip:
    """Test encrypt/decrypt roundtrip operations."""

    @pytest.fixture()
    def enc(self):
        """Create a FernetEncryption instance for testing."""
        key = FernetEncryption.generate_key()
        return FernetEncryption(key)

    def test_basic_roundtrip(self, enc):
        """Test basic encrypt then decrypt roundtrip."""
        plaintext = "my-secret-api-key"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_returns_bytes(self, enc):
        """Test that encrypt returns bytes."""
        encrypted = enc.encrypt("hello")

        assert isinstance(encrypted, bytes)

    def test_decrypt_returns_string(self, enc):
        """Test that decrypt returns a string."""
        encrypted = enc.encrypt("hello")
        decrypted = enc.decrypt(encrypted)

        assert isinstance(decrypted, str)

    def test_encrypted_differs_from_plaintext(self, enc):
        """Test that encrypted output differs from the plaintext bytes."""
        plaintext = "my-secret"
        encrypted = enc.encrypt(plaintext)

        assert encrypted != plaintext.encode()

    def test_encrypt_produces_different_ciphertexts(self, enc):
        """Test that encrypting same text twice produces different ciphertexts."""
        plaintext = "same-input"
        encrypted1 = enc.encrypt(plaintext)
        encrypted2 = enc.encrypt(plaintext)

        # Fernet includes a timestamp, so repeated encryptions differ
        assert encrypted1 != encrypted2

    def test_roundtrip_with_long_text(self, enc):
        """Test roundtrip with a long plaintext (10K characters)."""
        plaintext = "x" * 10_000
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_roundtrip_with_special_characters(self, enc):
        """Test roundtrip with special ASCII characters."""
        plaintext = '!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\~`'
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_roundtrip_with_whitespace(self, enc):
        """Test roundtrip with whitespace characters."""
        plaintext = "  tab\there\nnewline\r\nwindows  "
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_roundtrip_with_single_character(self, enc):
        """Test roundtrip with a single character."""
        encrypted = enc.encrypt("a")
        assert enc.decrypt(encrypted) == "a"

    def test_decrypt_accepts_string_ciphertext(self, enc):
        """Test that decrypt accepts string (base64) ciphertext."""
        plaintext = "test-value"
        encrypted_bytes = enc.encrypt(plaintext)
        encrypted_str = encrypted_bytes.decode()

        decrypted = enc.decrypt(encrypted_str)

        assert decrypted == plaintext

    def test_decrypt_accepts_bytes_ciphertext(self, enc):
        """Test that decrypt accepts bytes ciphertext."""
        plaintext = "test-value"
        encrypted = enc.encrypt(plaintext)

        assert isinstance(encrypted, bytes)
        assert enc.decrypt(encrypted) == plaintext


# =============================================================================
# encrypt_to_string / decrypt_from_string Tests
# =============================================================================


@pytest.mark.unit
class TestStringEncryptDecrypt:
    """Test encrypt_to_string and decrypt_from_string methods."""

    @pytest.fixture()
    def enc(self):
        """Create a FernetEncryption instance for testing."""
        key = FernetEncryption.generate_key()
        return FernetEncryption(key)

    def test_encrypt_to_string_returns_string(self, enc):
        """Test that encrypt_to_string returns a string."""
        result = enc.encrypt_to_string("test")

        assert isinstance(result, str)

    def test_string_roundtrip(self, enc):
        """Test encrypt_to_string then decrypt_from_string roundtrip."""
        plaintext = "my-api-key-12345"
        encrypted = enc.encrypt_to_string(plaintext)
        decrypted = enc.decrypt_from_string(encrypted)

        assert decrypted == plaintext

    def test_encrypted_string_is_valid_base64(self, enc):
        """Test that encrypted string is valid base64."""
        encrypted = enc.encrypt_to_string("test")

        # Should not raise
        base64.urlsafe_b64decode(encrypted)

    def test_string_methods_compatible_with_bytes_methods(self, enc):
        """Test that string methods produce compatible output with bytes methods."""
        plaintext = "cross-compatible"

        # Encrypt with bytes method, decrypt with string method
        encrypted_bytes = enc.encrypt(plaintext)
        decrypted = enc.decrypt_from_string(encrypted_bytes.decode())
        assert decrypted == plaintext

        # Encrypt with string method, decrypt with bytes method
        encrypted_str = enc.encrypt_to_string(plaintext)
        decrypted = enc.decrypt(encrypted_str.encode())
        assert decrypted == plaintext

    def test_string_roundtrip_with_long_text(self, enc):
        """Test string roundtrip with long text."""
        plaintext = "api-key-" * 500
        encrypted = enc.encrypt_to_string(plaintext)
        decrypted = enc.decrypt_from_string(encrypted)

        assert decrypted == plaintext


# =============================================================================
# Empty String Handling Tests
# =============================================================================


@pytest.mark.unit
class TestEmptyStringHandling:
    """Test behavior with empty strings."""

    @pytest.fixture()
    def enc(self):
        """Create a FernetEncryption instance for testing."""
        key = FernetEncryption.generate_key()
        return FernetEncryption(key)

    def test_encrypt_empty_string_returns_empty_bytes(self, enc):
        """Test that encrypting empty string returns b''."""
        result = enc.encrypt("")

        assert result == b""

    def test_decrypt_empty_bytes_returns_empty_string(self, enc):
        """Test that decrypting empty bytes returns ''."""
        result = enc.decrypt(b"")

        assert result == ""

    def test_decrypt_empty_string_returns_empty_string(self, enc):
        """Test that decrypting empty string returns ''."""
        result = enc.decrypt("")

        assert result == ""

    def test_encrypt_to_string_empty_returns_empty(self, enc):
        """Test that encrypt_to_string with empty input returns empty string."""
        result = enc.encrypt_to_string("")

        assert result == ""

    def test_decrypt_from_string_empty_returns_empty(self, enc):
        """Test that decrypt_from_string with empty input returns empty string."""
        result = enc.decrypt_from_string("")

        assert result == ""


# =============================================================================
# Wrong Key / Corrupted Ciphertext Tests
# =============================================================================


@pytest.mark.unit
class TestDecryptionFailures:
    """Test decryption failure scenarios."""

    def test_wrong_key_raises_invalid_token(self):
        """Test that decrypting with the wrong key raises InvalidToken."""
        key1 = FernetEncryption.generate_key()
        key2 = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key1)
        enc2 = FernetEncryption(key2)

        encrypted = enc1.encrypt("secret-data")

        with pytest.raises(InvalidToken):
            enc2.decrypt(encrypted)

    def test_wrong_key_raises_invalid_token_string_methods(self):
        """Test that wrong key fails with string encrypt/decrypt methods."""
        key1 = FernetEncryption.generate_key()
        key2 = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key1)
        enc2 = FernetEncryption(key2)

        encrypted = enc1.encrypt_to_string("secret-data")

        with pytest.raises(InvalidToken):
            enc2.decrypt_from_string(encrypted)

    def test_corrupted_ciphertext_raises_error(self):
        """Test that corrupted ciphertext raises an error."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)
        encrypted = enc.encrypt("test")

        corrupted = encrypted[:-5] + b"XXXXX"

        with pytest.raises(Exception):
            enc.decrypt(corrupted)

    def test_random_bytes_raises_error(self):
        """Test that decrypting random bytes raises an error."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        with pytest.raises(Exception):
            enc.decrypt(b"this-is-not-a-valid-fernet-token")

    def test_truncated_ciphertext_raises_error(self):
        """Test that truncated ciphertext raises an error."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)
        encrypted = enc.encrypt("test-data")

        truncated = encrypted[: len(encrypted) // 2]

        with pytest.raises(Exception):
            enc.decrypt(truncated)

    def test_modified_single_byte_raises_error(self):
        """Test that flipping a single byte in ciphertext raises an error."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)
        encrypted = enc.encrypt("sensitive-data")

        encrypted_list = bytearray(encrypted)
        mid = len(encrypted_list) // 2
        encrypted_list[mid] ^= 0xFF
        modified = bytes(encrypted_list)

        with pytest.raises(Exception):
            enc.decrypt(modified)


# =============================================================================
# Key Fingerprint Tests
# =============================================================================


@pytest.mark.unit
class TestKeyFingerprint:
    """Test key_fingerprint property."""

    def test_fingerprint_returns_string(self):
        """Test that key_fingerprint returns a string."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        assert isinstance(enc.key_fingerprint, str)

    def test_fingerprint_is_8_characters(self):
        """Test that fingerprint is exactly 8 characters."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        assert len(enc.key_fingerprint) == 8

    def test_fingerprint_is_hexadecimal(self):
        """Test that fingerprint consists only of hexadecimal characters."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        # Should not raise ValueError
        int(enc.key_fingerprint, 16)

    def test_fingerprint_is_deterministic(self):
        """Test that the same key always produces the same fingerprint."""
        key = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key)
        enc2 = FernetEncryption(key)

        assert enc1.key_fingerprint == enc2.key_fingerprint

    def test_fingerprint_differs_for_different_keys(self):
        """Test that different keys produce different fingerprints."""
        key1 = FernetEncryption.generate_key()
        key2 = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key1)
        enc2 = FernetEncryption(key2)

        assert enc1.key_fingerprint != enc2.key_fingerprint

    def test_fingerprint_matches_sha256_prefix(self):
        """Test that fingerprint matches first 8 chars of SHA256 hash of key bytes."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        expected = hashlib.sha256(key.encode()).hexdigest()[:8]

        assert enc.key_fingerprint == expected

    def test_fingerprint_consistent_string_and_bytes_init(self):
        """Test that fingerprint is identical for string and bytes key init."""
        key_str = FernetEncryption.generate_key()
        key_bytes = key_str.encode()
        enc_str = FernetEncryption(key_str)
        enc_bytes = FernetEncryption(key_bytes)

        assert enc_str.key_fingerprint == enc_bytes.key_fingerprint

    def test_fingerprint_does_not_expose_key(self):
        """Test that fingerprint does not contain the actual key."""
        key = FernetEncryption.generate_key()
        enc = FernetEncryption(key)

        assert enc.key_fingerprint not in key


# =============================================================================
# Unicode / International Text Tests
# =============================================================================


@pytest.mark.unit
class TestUnicodeSupport:
    """Test encryption/decryption of Unicode text including German umlauts."""

    @pytest.fixture()
    def enc(self):
        """Create a FernetEncryption instance for testing."""
        key = FernetEncryption.generate_key()
        return FernetEncryption(key)

    def test_german_umlauts(self, enc):
        """Test roundtrip with German umlauts (ae, oe, ue, AE, OE, UE)."""
        plaintext = "Schl\u00fcssel mit Umlauten: \u00e4\u00f6\u00fc\u00c4\u00d6\u00dc"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_german_sharp_s_and_special_quotes(self, enc):
        """Test roundtrip with sharp s (ss) and German typographic quotes."""
        plaintext = "Stra\u00dfe, Gr\u00f6\u00dfe, Ma\u00dfe \u2013 \u201eZitat\u201c und \u201aEinzel\u2018"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_emoji_roundtrip(self, enc):
        """Test roundtrip with emoji characters (4-byte UTF-8)."""
        plaintext = "Hello \U0001f30d! Status: \u2705 Rocket: \U0001f680"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_mixed_unicode_scripts(self, enc):
        """Test roundtrip with mixed Unicode scripts."""
        plaintext = "English \u00c4\u00d6\u00dc\u00df \u4e16\u754c \u4e16\u754c \ud55c\uad6d\uc5b4"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_unicode_with_string_methods(self, enc):
        """Test German umlauts with encrypt_to_string/decrypt_from_string."""
        plaintext = "Geheime Schl\u00fcsselw\u00f6rter: \u00e4u\u00dferst vertraulich"
        encrypted = enc.encrypt_to_string(plaintext)
        decrypted = enc.decrypt_from_string(encrypted)

        assert decrypted == plaintext

    def test_multibyte_utf8_characters(self, enc):
        """Test with characters requiring 1, 2, 3, and 4 byte UTF-8 encodings."""
        # A (1 byte), \u00e9 e-acute (2 bytes), \u4e16 CJK (3 bytes), \U0001f600 grinning (4 bytes)
        plaintext = "A \u00e9 \u4e16 \U0001f600"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext

    def test_null_bytes_in_text(self, enc):
        """Test roundtrip with null bytes embedded in text."""
        plaintext = "before\x00after"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext


# =============================================================================
# ImportError Handling Tests
# =============================================================================


@pytest.mark.unit
class TestImportErrorHandling:
    """Test behavior when cryptography package is not installed."""

    def test_init_raises_import_error_without_cryptography(self):
        """Test that __init__ raises ImportError if cryptography is missing."""
        original_modules = {}
        modules_to_remove = [
            key for key in sys.modules if key.startswith("cryptography")
        ]
        for mod_name in modules_to_remove:
            original_modules[mod_name] = sys.modules.pop(mod_name)

        encryption_module_key = "eq_chatbot_core.security.encryption"
        original_encryption = sys.modules.pop(encryption_module_key, None)

        try:
            original_import = (
                __builtins__.__import__
                if hasattr(__builtins__, "__import__")
                else __import__
            )

            def mock_import(name, *args, **kwargs):
                if name == "cryptography.fernet" or name.startswith("cryptography"):
                    raise ImportError("No module named 'cryptography'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                import importlib

                try:
                    module = importlib.import_module(
                        "eq_chatbot_core.security.encryption"
                    )
                    klass = module.FernetEncryption

                    with pytest.raises(ImportError, match="cryptography"):
                        klass("some-key")
                except ImportError:
                    # Module itself failing to import is also acceptable
                    pass
        finally:
            sys.modules.update(original_modules)
            if original_encryption is not None:
                sys.modules[encryption_module_key] = original_encryption


# =============================================================================
# Edge Case and Stress Tests
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture()
    def enc(self):
        """Create a FernetEncryption instance for testing."""
        key = FernetEncryption.generate_key()
        return FernetEncryption(key)

    def test_very_long_plaintext(self, enc):
        """Test encryption of very long plaintext (100KB)."""
        plaintext = "A" * 100_000
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == plaintext
        assert len(decrypted) == 100_000

    def test_single_space(self, enc):
        """Test encryption of a single space character."""
        encrypted = enc.encrypt(" ")
        assert enc.decrypt(encrypted) == " "

    def test_newline_only(self, enc):
        """Test encryption of a newline-only string."""
        encrypted = enc.encrypt("\n")
        assert enc.decrypt(encrypted) == "\n"

    def test_multiple_sequential_operations(self, enc):
        """Test 100 sequential encrypt/decrypt operations."""
        for i in range(100):
            plaintext = f"message-{i}"
            encrypted = enc.encrypt(plaintext)
            assert enc.decrypt(encrypted) == plaintext

    def test_json_content_roundtrip(self, enc):
        """Test roundtrip with JSON-formatted content."""
        plaintext = '{"api_key": "sk-12345", "model": "gpt-4"}'
        encrypted = enc.encrypt(plaintext)
        assert enc.decrypt(encrypted) == plaintext

    def test_url_content_roundtrip(self, enc):
        """Test roundtrip with URL content."""
        plaintext = "https://api.example.com/v1/chat?token=abc123&user=test"
        encrypted = enc.encrypt(plaintext)
        assert enc.decrypt(encrypted) == plaintext

    def test_multiline_text_roundtrip(self, enc):
        """Test roundtrip with multiline text."""
        plaintext = "Line 1\nLine 2\nLine 3\n\nLine 5"
        encrypted = enc.encrypt(plaintext)
        assert enc.decrypt(encrypted) == plaintext

    def test_falsy_ciphertext_returns_empty(self, enc):
        """Test that falsy ciphertext values return empty string."""
        assert enc.decrypt(b"") == ""
        assert enc.decrypt("") == ""

    def test_independent_instances_same_key_cross_decrypt(self):
        """Test that two instances with the same key can cross-decrypt."""
        key = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key)
        enc2 = FernetEncryption(key)

        plaintext = "shared-secret"
        encrypted_by_1 = enc1.encrypt(plaintext)
        encrypted_by_2 = enc2.encrypt(plaintext)

        assert enc2.decrypt(encrypted_by_1) == plaintext
        assert enc1.decrypt(encrypted_by_2) == plaintext


# =============================================================================
# Real-World Usage Scenario Tests
# =============================================================================


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test real-world usage patterns for API key encryption."""

    def test_api_key_storage_workflow(self):
        """Test complete API key storage and retrieval workflow."""
        master_key = FernetEncryption.generate_key()

        # Encrypt API key for storage
        enc = FernetEncryption(master_key)
        api_key = "sk-proj-abcdefghij1234567890"
        stored_value = enc.encrypt_to_string(api_key)

        # Later: retrieve and decrypt with new instance
        enc2 = FernetEncryption(master_key)
        retrieved_key = enc2.decrypt_from_string(stored_value)

        assert retrieved_key == api_key

    def test_multiple_keys_encrypted_with_same_master(self):
        """Test encrypting multiple API keys with one master key."""
        master_key = FernetEncryption.generate_key()
        enc = FernetEncryption(master_key)

        keys = {
            "openai": "sk-openai-12345",
            "anthropic": "sk-ant-67890",
            "langdock": "ld-abcdef",
        }

        encrypted_keys = {
            name: enc.encrypt_to_string(value) for name, value in keys.items()
        }
        decrypted_keys = {
            name: enc.decrypt_from_string(value)
            for name, value in encrypted_keys.items()
        }

        assert decrypted_keys == keys

    def test_key_rotation_scenario(self):
        """Test rotating encryption keys."""
        old_key = FernetEncryption.generate_key()
        new_key = FernetEncryption.generate_key()

        old_enc = FernetEncryption(old_key)
        new_enc = FernetEncryption(new_key)

        # Data encrypted with old key
        api_key = "sk-my-secret-key"
        old_encrypted = old_enc.encrypt_to_string(api_key)

        # Re-encrypt with new key
        decrypted = old_enc.decrypt_from_string(old_encrypted)
        new_encrypted = new_enc.encrypt_to_string(decrypted)

        # New key works
        assert new_enc.decrypt_from_string(new_encrypted) == api_key

        # Old key cannot decrypt new ciphertext
        with pytest.raises(InvalidToken):
            old_enc.decrypt_from_string(new_encrypted)

    def test_fingerprint_for_key_identification(self):
        """Test using fingerprints to identify which key was used."""
        key1 = FernetEncryption.generate_key()
        key2 = FernetEncryption.generate_key()
        enc1 = FernetEncryption(key1)
        enc2 = FernetEncryption(key2)

        fp1 = enc1.key_fingerprint
        fp2 = enc2.key_fingerprint

        assert fp1 != fp2
        assert len(fp1) == 8
        assert len(fp2) == 8
