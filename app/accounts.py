"""
NanoNets API Accounts Manager

Manages multiple API accounts for failover support.
Lock file format: account_id:record_id (e.g., "2:1627690")
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Account configuration
ACCOUNTS = {
    1: os.getenv("API_KEY_1"),
    2: os.getenv("API_KEY_2"),
    3: os.getenv("API_KEY_3"),
    4: os.getenv("API_KEY_4"),
}

# Filter out None values (missing keys)
ACCOUNTS = {k: v for k, v in ACCOUNTS.items() if v}


def get_api_key(account_id: int) -> str:
    """Get API key by account ID."""
    key = ACCOUNTS.get(account_id)
    if not key:
        raise ValueError(f"No API key found for account {account_id}")
    return key


def get_all_accounts() -> list:
    """Get list of (account_id, api_key) tuples in failover order."""
    return [(aid, key) for aid, key in sorted(ACCOUNTS.items())]


def get_account_count() -> int:
    """Get number of configured accounts."""
    return len(ACCOUNTS)


def parse_lock_file(content: str) -> tuple:
    """
    Parse lock file content.
    Returns (account_id, record_id) tuple.
    Supports both old format (just record_id) and new format (account_id:record_id).
    """
    content = content.strip()
    if ':' in content:
        parts = content.split(':', 1)
        return int(parts[0]), parts[1]
    else:
        # Old format - assume account 2 (was the active one)
        return 2, content


def format_lock_content(account_id: int, record_id: str) -> str:
    """Format content for lock file."""
    return f"{account_id}:{record_id}"
