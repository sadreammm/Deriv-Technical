"""
Utility: SHA-256 prompt hashing for audit trail and deduplication.
"""

import hashlib

def hash_prompt(text: str) -> str:
    """Return a 16-char hex SHA-256 digest of the given prompt string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
