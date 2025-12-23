import os
import re
import time
import requests
from requests.exceptions import SSLError, ConnectionError, Timeout
from .accounts import get_all_accounts, get_api_key, parse_lock_file, format_lock_content


def convert_file(file_path, output_dir):
    """
    Handles the simple, one-shot conversion for a single file.
    Used for --convert-only mode.
    """
    print(f"  -> Uploading '{os.path.basename(file_path)}'...")
    upload_chunk(file_path, output_dir)

    print(f"  -> Retrieving '{os.path.basename(file_path)}'...")
    return retrieve_chunk(file_path, output_dir)


def upload_chunk(file_path, output_dir):
    """
    Uploads a single file chunk with failover across all configured accounts.
    Saves account_id:record_id to lock file.
    Skips if a lock file already exists or if the final MD file exists.
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    lock_file_path = os.path.join(output_dir, f"{base_name}.pdf.lock")
    output_md_path = os.path.join(output_dir, f"{base_name}.md")

    # First, check if the final output already exists and there's no lock file
    if os.path.exists(output_md_path) and not os.path.exists(lock_file_path):
        print(f"  -> Markdown file already exists for {base_name}. Skipping upload.")
        return True

    # Then, check if it's currently being processed
    if os.path.exists(lock_file_path):
        print(f"  -> Lock file already exists for {base_name}. Skipping upload.")
        return True

    # Try each account until one succeeds
    accounts = get_all_accounts()
    if not accounts:
        print(f"  x No API accounts configured!")
        return False

    for account_id, api_key in accounts:
        print(f"  -> Trying account {account_id}...")
        record_id, should_continue = upload_file(file_path, api_key)

        if record_id:
            print(f"  -> File uploaded via account {account_id}. Record ID: {record_id}")
            lock_content = format_lock_content(account_id, record_id)
            with open(lock_file_path, "w") as f:
                f.write(lock_content)
            print(f"  -> Created lock file for {base_name}.")
            return True

        if not should_continue:
            # Non-recoverable error, don't try other accounts
            break

        # Rate limit or similar - try next account
        print(f"  -> Account {account_id} unavailable, trying next...")

    print(f"  x Failed to upload file {base_name} (all accounts exhausted)")
    return False


def retrieve_chunk(file_path, output_dir):
    """
    Retrieves a single file chunk using the account_id:record_id from its lock file.
    Returns the file path on success, a status string if not complete, or None on error.
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    lock_file_path = os.path.join(output_dir, f"{base_name}.pdf.lock")
    output_md_path = os.path.join(output_dir, f"{base_name}.md")

    if not os.path.exists(lock_file_path):
        print(f"  x No lock file found for {base_name}. Cannot retrieve.")
        return None

    with open(lock_file_path, "r") as f:
        lock_content = f.read().strip()

    if not lock_content:
        print(f"  x Lock file for {base_name} is empty. Cannot retrieve.")
        return None

    # Parse lock file (supports both old and new format)
    account_id, record_id = parse_lock_file(lock_content)

    try:
        api_key = get_api_key(account_id)
    except ValueError as e:
        print(f"  x {e}")
        return None

    # Get total pages for progress reporting
    total_pages = 0
    try:
        match = re.search(r'_pages_(\d+)_(\d+)\.pdf$', os.path.basename(file_path))
        if match:
            total_pages = int(match.group(2)) - int(match.group(1)) + 1
    except Exception:
        pass

    result = check_status_and_retrieve(record_id, api_key, total_pages=total_pages)

    # If result is a status string (e.g., "processing"), return it directly
    if result in ["processing", "failed"]:
        return result

    # If result is None (error), return None
    if result is None:
        print(f"  x Failed to retrieve content for {base_name} (Account: {account_id}, Record ID: {record_id})")
        return None

    # Otherwise, result is the markdown content
    markdown_content = result
    print(f"  -> Content retrieved for {base_name}.")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"  -> Saved to: {output_md_path}")

    os.remove(lock_file_path)
    print(f"  -> Removed lock file for {base_name}.")

    return output_md_path


def upload_file(file_path, api_key, max_retries=3, retry_delay=5):
    """
    Upload file to NanoNets API for async processing.
    Returns (record_id, should_continue) tuple.
    - record_id: the ID on success, None on failure
    - should_continue: True if should try next account (rate limit), False otherwise
    Includes retry logic for transient errors (SSL, connection, timeout).
    """
    url = "https://extraction-api.nanonets.com/extract-async"
    headers = {"Authorization": f"Bearer {api_key}"}

    # Errors that warrant a retry
    retryable_exceptions = (SSLError, ConnectionError, Timeout)

    for attempt in range(1, max_retries + 1):
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {
                    "output_type": "markdown",
                    "model_type": "nanonets"
                }

                response = requests.post(url, headers=headers, files=files, data=data, timeout=300)

                # Handle rate limiting (429) - try next account
                if response.status_code == 429:
                    try:
                        error_detail = response.json().get('detail', 'Rate limit exceeded')
                    except ValueError:
                        error_detail = response.text or 'Rate limit exceeded'
                    print(f"  x API Rate Limit: {error_detail}")
                    return None, True  # Try next account

                # Handle access errors (403) - try next account
                if response.status_code == 403:
                    try:
                        error_detail = response.json().get('detail', 'Access forbidden')
                    except ValueError:
                        error_detail = response.text or 'Access forbidden'
                    print(f"  x API Access Error: {error_detail}")
                    return None, True  # Try next account

                # Handle server errors (5xx) - these might be transient
                if response.status_code >= 500:
                    try:
                        error_detail = response.json().get('detail', f'Server error {response.status_code}')
                    except ValueError:
                        error_detail = response.text or f'Server error {response.status_code}'
                    print(f"  x API Server Error: {error_detail}")
                    if attempt < max_retries:
                        print(f"  ~ Retrying in {retry_delay}s... (attempt {attempt}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    return None, True  # Try next account after retries exhausted

                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    return result.get("record_id"), False
                else:
                    error_msg = result.get('message') or result.get('detail') or 'Unknown error'
                    print(f"  x Upload failed: {error_msg}")
                    return None, False  # Don't try next account for API errors

        except retryable_exceptions as e:
            error_type = type(e).__name__
            print(f"  x {error_type}: {e}")
            if attempt < max_retries:
                print(f"  ~ Retrying in {retry_delay}s... (attempt {attempt}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  x Max retries ({max_retries}) exceeded.")
                return None, True  # Try next account

        except requests.exceptions.RequestException as e:
            print(f"  x Request error: {e}")
            # Try to get more details from the response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', e.response.text)
                except ValueError:
                    error_detail = e.response.text
                if error_detail:
                    print(f"  -> API message: {error_detail}")
            return None, False

        except Exception as e:
            print(f"  x Error uploading file: {e}")
            return None, False

    return None, True


def check_status_and_retrieve(record_id, api_key, total_pages=0, max_retries=3, retry_delay=5):
    """
    Checks the API status once and retrieves the result if completed.
    Does not poll. Returns content on success, status string if processing,
    or None on failure.
    Includes retry logic for transient errors (SSL, connection, timeout, 5xx).
    """
    url = f"https://extraction-api.nanonets.com/files/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    # Errors that warrant a retry
    retryable_exceptions = (SSLError, ConnectionError, Timeout)

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=60)

            # Handle rate limiting (429)
            if response.status_code == 429:
                try:
                    error_detail = response.json().get('detail', 'Rate limit exceeded')
                except ValueError:
                    error_detail = response.text or 'Rate limit exceeded'
                print(f"  x API Rate Limit: {error_detail}")
                return None

            # Handle access errors (403)
            if response.status_code == 403:
                try:
                    error_detail = response.json().get('detail', 'Access forbidden')
                except ValueError:
                    error_detail = response.text or 'Access forbidden'
                print(f"  x API Access Error: {error_detail}")
                return None

            # Handle server errors (5xx) - these might be transient
            if response.status_code >= 500:
                try:
                    error_detail = response.json().get('detail', f'Server error {response.status_code}')
                except ValueError:
                    error_detail = response.text or f'Server error {response.status_code}'
                print(f"  x API Server Error: {error_detail}")
                if attempt < max_retries:
                    print(f"  ~ Retrying in {retry_delay}s... (attempt {attempt}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                return None

            response.raise_for_status()
            result = response.json()

            if not result.get("success"):
                error_detail = result.get('detail', 'Unknown error')
                print(f"  x API returned error: {error_detail}")
                return None

            status = result.get("processing_status") or result.get("status")

            if status == "completed":
                print(f"  -> Status: completed.")
                content = result.get("content", "")
                if not content:
                    print(f"  ! Warning: Content is empty in completed response.")
                return content
            elif status in ["processing", "failed"]:
                progress_info = ""
                if status == "processing" and total_pages > 0:
                    pages_done = result.get("pages_processed", 0)
                    proc_time = result.get("processing_time", 0.0)
                    progress_info = f" (page {pages_done}/{total_pages} - {proc_time:.2f}s)"
                print(f"  -> Status: {status}{progress_info}. Will check again later.")
                return status
            else:
                print(f"  ! Unknown status: {status}")
                return status

        except retryable_exceptions as e:
            error_type = type(e).__name__
            print(f"  x {error_type}: {e}")
            if attempt < max_retries:
                print(f"  ~ Retrying in {retry_delay}s... (attempt {attempt}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  x Max retries ({max_retries}) exceeded.")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  x Request error while checking status: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', e.response.text)
                except ValueError:
                    error_detail = e.response.text
                if error_detail:
                    print(f"  -> API message: {error_detail}")
            return None

        except Exception as e:
            print(f"  x Error while checking status: {e}")
            return None

    return None


def get_file_status(record_id, api_key):
    """
    Retrieves the status and metadata for a specific record_id from the API.
    """
    url = f"https://extraction-api.nanonets.com/files/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  x Request error for record_id {record_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                return e.response.json()
            except ValueError:
                return {"success": False, "detail": e.response.text}
        return None
    except Exception as e:
        print(f"  x An unexpected error occurred for record_id {record_id}: {e}")
        return None
