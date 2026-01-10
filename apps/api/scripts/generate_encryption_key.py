#!/usr/bin/env python3
"""
Generate encryption key for token encryption.

Run this script to generate a secure encryption key for TOKEN_ENCRYPTION_KEY.
Save the output to your .env file.
"""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print("=" * 70)
    print("TOKEN ENCRYPTION KEY")
    print("=" * 70)
    print(f"\nAdd this to your .env file:")
    print(f"\nTOKEN_ENCRYPTION_KEY={key.decode()}\n")
    print("=" * 70)
    print("\n⚠️  IMPORTANT:")
    print("- Keep this key secure and never commit it to version control")
    print("- Use the same key across all environments (dev/staging/prod)")
    print("- If you lose this key, all encrypted tokens will be unrecoverable")
    print("=" * 70)

