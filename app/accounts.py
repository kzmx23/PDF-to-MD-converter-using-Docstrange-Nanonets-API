"""
NanoNets API Accounts Manager

Manages multiple API accounts for failover support.
Lock file format: account_id:record_id:start_time:last_check_time:pages_processed
Example: "3:1627690:2024-01-29-10-30:2024-01-29-11-45:40"

Old formats (account_id:record_id or with Unix timestamps) are still supported.
"""

import os
import time
from datetime import datetime
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


def _parse_time(time_str: str) -> int:
    """
    Parse time string to Unix timestamp.
    Supports both human-readable format (yyyy-mm-dd-hh-mm) and Unix timestamps.
    """
    if not time_str or time_str == '0':
        return 0

    # Check if it's a Unix timestamp (all digits)
    if time_str.isdigit():
        return int(time_str)

    # Parse human-readable format: yyyy-mm-dd-hh-mm
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d-%H-%M")
        return int(dt.timestamp())
    except ValueError:
        return 0


def _format_time(ts: int) -> str:
    """
    Format Unix timestamp to human-readable string (yyyy-mm-dd-hh-mm).
    """
    if ts == 0:
        return "0"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d-%H-%M")


def parse_lock_file(content: str) -> dict:
    """
    Parse lock file content.
    Returns dict with keys: account_id, record_id, start_ts, last_check_ts, pages_processed.
    Supports old format (account_id:record_id) and new extended format with human-readable times.
    """
    content = content.strip()
    parts = content.split(':')

    result = {
        'account_id': 2,  # Default for very old format
        'record_id': content,
        'start_ts': 0,
        'last_check_ts': 0,
        'pages_processed': 0,
    }

    if len(parts) >= 2:
        result['account_id'] = int(parts[0])
        result['record_id'] = parts[1]

    if len(parts) >= 3:
        result['start_ts'] = _parse_time(parts[2])

    if len(parts) >= 4:
        result['last_check_ts'] = _parse_time(parts[3])

    if len(parts) >= 5:
        result['pages_processed'] = int(parts[4])

    return result


def format_lock_content(account_id: int, record_id: str, start_ts: int = None,
                        last_check_ts: int = None, pages_processed: int = 0) -> str:
    """
    Format content for lock file with extended metadata.
    Uses human-readable time format: yyyy-mm-dd-hh-mm
    """
    if start_ts is None:
        start_ts = int(time.time())
    if last_check_ts is None:
        last_check_ts = start_ts

    start_str = _format_time(start_ts)
    last_check_str = _format_time(last_check_ts)

    return f"{account_id}:{record_id}:{start_str}:{last_check_str}:{pages_processed}"


def is_stuck(lock_data: dict, stuck_threshold_hours: float = 2.0) -> bool:
    """
    Check if a file is stuck (no progress for specified hours).
    Returns True if stuck.
    """
    if lock_data['last_check_ts'] == 0:
        # Old format lock file, can't determine if stuck
        return False

    current_time = int(time.time())
    time_since_last_check = current_time - lock_data['last_check_ts']
    threshold_seconds = stuck_threshold_hours * 3600

    # Consider stuck if last check was more than threshold ago
    # AND pages haven't changed (we can't track old pages here, so just use time)
    return time_since_last_check > threshold_seconds
