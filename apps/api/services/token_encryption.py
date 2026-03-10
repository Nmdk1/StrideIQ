"""
Token Encryption Service

Encrypts and decrypts OAuth tokens (Strava, Garmin) using Fernet symmetric encryption.
All tokens are encrypted at rest in the database.

ARCHITECTURE:
- Uses cryptography library (Fernet)
- Encryption key from environment variable (TOKEN_ENCRYPTION_KEY)
- Never stores plain credentials
"""

from cryptography.fernet import Fernet
from typing import Optional
import os
import logging
from core.config import settings

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Handles encryption/decryption of OAuth tokens."""
    
    def __init__(self):
        """Initialize encryption with key from environment."""
        encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")
        
        if not encryption_key:
            # SECURITY: Fail hard in production - no auto-generated keys
            environment = os.getenv("ENVIRONMENT", "development")
            if environment == "production":
                raise RuntimeError(
                    "TOKEN_ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            # Generate a key if not set (for development only)
            logger.warning("TOKEN_ENCRYPTION_KEY not set. Generating temporary key (NOT FOR PRODUCTION)")
            encryption_key = Fernet.generate_key().decode()
            # Don't log the actual key - security risk even in dev
            logger.warning("Set TOKEN_ENCRYPTION_KEY environment variable for production!")
        
        # Ensure key is bytes
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        
        try:
            self.cipher = Fernet(encryption_key)
        except Exception as e:
            logger.error(f"Failed to initialize Fernet cipher: {e}")
            raise ValueError(f"Invalid encryption key format: {e}")
    
    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypt a plaintext token.
        
        Args:
            plaintext: Plain text token to encrypt
            
        Returns:
            Encrypted token (base64 string) or None if encryption fails
        """
        if not plaintext:
            return None
        
        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            return None
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt an encrypted token.
        
        Args:
            ciphertext: Encrypted token (base64 string)
            
        Returns:
            Decrypted token (plain text) or None if decryption fails
        """
        if not ciphertext:
            return None
        
        try:
            decrypted = self.cipher.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            return None
    
    def is_encrypted(self, token: Optional[str]) -> bool:
        """
        Check if a token appears to be encrypted.
        
        Args:
            token: Token string to check
            
        Returns:
            True if token appears encrypted, False otherwise
        """
        if not token:
            return False
        
        # Encrypted tokens are base64 strings with specific format
        # Simple heuristic: encrypted tokens are longer and contain base64 chars
        try:
            # Try to decode as base64
            import base64
            base64.b64decode(token)
            # If it decodes successfully and is reasonably long, likely encrypted
            return len(token) > 20
        except:
            return False


# Global instance
_token_encryption: Optional[TokenEncryption] = None


def get_token_encryption() -> TokenEncryption:
    """Get or create global token encryption instance."""
    global _token_encryption
    if _token_encryption is None:
        _token_encryption = TokenEncryption()
    return _token_encryption


def encrypt_token(token: Optional[str]) -> Optional[str]:
    """Convenience function to encrypt a token."""
    if not token:
        return None
    return get_token_encryption().encrypt(token)


def decrypt_token(token: Optional[str]) -> Optional[str]:
    """Convenience function to decrypt a token."""
    if not token:
        return None
    return get_token_encryption().decrypt(token)

