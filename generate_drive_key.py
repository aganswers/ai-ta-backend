#!/usr/bin/env python3
"""
Generate encryption key for Google Drive token storage.
Run this once and add the output to your .env file as DRIVE_TOKEN_ENCRYPTION_KEY.
"""

import base64
import os

# Generate a 32-byte key for AES-256
key = os.urandom(32)
key_b64 = base64.b64encode(key).decode()

print("Add this to your .env file:")
print(f"DRIVE_TOKEN_ENCRYPTION_KEY={key_b64}")
