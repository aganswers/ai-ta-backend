"""
Utility functions for drive integrations.
Handles token encryption, authentication helpers, and common operations.
"""

import base64
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_encryption_key() -> bytes:
    """Get the encryption key from environment variables."""
    key_b64 = os.environ.get('DRIVE_TOKEN_ENCRYPTION_KEY')
    if not key_b64:
        raise ValueError("DRIVE_TOKEN_ENCRYPTION_KEY not set in environment")
    return base64.b64decode(key_b64)


def encrypt_token(data: dict) -> str:
    """Encrypt token data using AES-GCM."""
    key = get_encryption_key()
    nonce = os.urandom(12)
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, json.dumps(data).encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_token(encrypted_data: str) -> dict:
    """Decrypt token data using AES-GCM."""
    key = get_encryption_key()
    raw = base64.b64decode(encrypted_data)
    nonce, ciphertext = raw[:12], raw[12:]
    cipher = AESGCM(key)
    plaintext = cipher.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode())


def utcnow() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def expires_in(seconds: int) -> datetime:
    """Get datetime that expires in given seconds."""
    return utcnow() + timedelta(seconds=seconds)


def should_refresh_token(expires_at: Optional[datetime], buffer_seconds: int = 300) -> bool:
    """Check if token should be refreshed (5 min buffer by default)."""
    if not expires_at:
        return True
    return utcnow() > (expires_at - timedelta(seconds=buffer_seconds))


def retryable_request(request_func, max_retries: int = 3, backoff_factor: float = 0.5):
    """Execute a request with exponential backoff retry logic."""
    for attempt in range(max_retries):
        response = request_func()
        
        # Success or client error - don't retry
        if response.status_code < 500 and response.status_code != 429:
            return response
            
        # Server error or rate limit - retry with backoff
        if attempt < max_retries - 1:
            wait_time = backoff_factor * (2 ** attempt)
            time.sleep(wait_time)
    
    return response


def get_user_email_from_request(request) -> Optional[str]:
    """
    Extract user email from request headers or session.
    For now, we'll use a simple header-based approach.
    """
    # Try different header formats
    user_email = request.headers.get('X-User-Email')
    if user_email:
        return user_email
    
    # Try to extract from Clerk session cookie
    session_cookie = request.cookies.get('__session')
    if session_cookie:
        try:
            import jwt
            # Decode without verification for development (NOT for production)
            decoded = jwt.decode(session_cookie, options={"verify_signature": False})
            user_id = decoded.get('sub')  # Clerk user ID
            if user_id:
                # For now, create a deterministic email from user ID
                return f"user_{user_id[-8:]}@clerk.local"
        except Exception as e:
            print(f"Failed to decode Clerk session: {e}")
    
    # Fallback to a test user for development
    # TODO: Implement proper Clerk token validation
    return "test@example.com"


def validate_course_access(course_name: str, user_email: str, supabase_client) -> bool:
    """
    Validate that user has access to the specified course.
    For now, allow access if course exists.
    """
    try:
        # Simple check - if course exists, allow access
        response = supabase_client.table('projects').select('course_name').eq('course_name', course_name).execute()
        print(f"🔧 Course access check: course_name='{course_name}', found {len(response.data)} matches")
        if len(response.data) > 0:
            print(f"✅ Course access granted for: {course_name}")
            return True
        else:
            print(f"❌ Course not found in projects table: {course_name}")
            # For development, let's allow access anyway
            print("🔧 Development mode: allowing access anyway")
            return True
    except Exception as e:
        print(f"Course access validation error: {e}")
        # For development, allow access
        return True
