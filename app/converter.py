import os
import time
import requests

import os
import re
import time
import requests

def convert_file(file_path, output_dir, api_key, retrieve_only=False):
    """
    Handles the simple, one-shot conversion for a single file.
    Used for --convert-only mode.
    """
    print(f"  → Uploading '{os.path.basename(file_path)}'...")
    upload_chunk(file_path, output_dir, api_key)
    
    print(f"  → Retrieving '{os.path.basename(file_path)}'...")
    return retrieve_chunk(file_path, output_dir, api_key)


def upload_chunk(file_path, output_dir, api_key):
    """
    Uploads a single file chunk and saves its record_id to a lock file.
    Skips if a lock file already exists or if the final MD file exists.
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    lock_file_path = os.path.join(output_dir, f"{base_name}.pdf.lock")
    output_md_path = os.path.join(output_dir, f"{base_name}.md")

    # First, check if the final output already exists and there's no lock file
    if os.path.exists(output_md_path) and not os.path.exists(lock_file_path):
        print(f"  → Markdown file already exists for {base_name}. Skipping upload.")
        return

    # Then, check if it's currently being processed
    if os.path.exists(lock_file_path):
        print(f"  → Lock file already exists for {base_name}. Skipping upload.")
        return

    record_id = upload_file(file_path, api_key)

    if not record_id:
        print(f"  ✗ Failed to upload file {base_name}")
        return

    print(f"  → File uploaded. Record ID: {record_id}")
    with open(lock_file_path, "w") as f:
        f.write(str(record_id))
    print(f"  → Created lock file for {base_name}.")


def retrieve_chunk(file_path, output_dir, api_key):
    """
    Retrieves a single file chunk using the record_id from its lock file.
    Returns the file path on success, a status string if not complete, or None on error.
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    lock_file_path = os.path.join(output_dir, f"{base_name}.pdf.lock")
    output_md_path = os.path.join(output_dir, f"{base_name}.md")

    if not os.path.exists(lock_file_path):
        print(f"  ✗ No lock file found for {base_name}. Cannot retrieve.")
        return None

    with open(lock_file_path, "r") as f:
        record_id = f.read().strip()

    if not record_id:
        print(f"  ✗ Lock file for {base_name} is empty. Cannot retrieve.")
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
        print(f"  ✗ Failed to retrieve content for {base_name} (Record ID: {record_id})")
        return None

    # Otherwise, result is the markdown content
    markdown_content = result
    print(f"  → Content retrieved for {base_name}.")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"  → Saved to: {output_md_path}")
    
    os.remove(lock_file_path)
    print(f"  → Removed lock file for {base_name}.")
    
    return output_md_path



def upload_file(file_path, api_key):
    """
    Upload file to NanoNets API for async processing.
    Returns record_id on success, None on failure.
    """
    url = "https://extraction-api.nanonets.com/extract-async"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "output_type": "markdown",
                "model_type": "nanonets"
            }

            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()

            result = response.json()

            if result.get("success"):
                return result.get("record_id")
            else:
                print(f"  ✗ Upload failed: {result.get('message', 'Unknown error')}")
                return None

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request error: {e}")
        if hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"  ✗ Error uploading file: {e}")
        return None


def check_status_and_retrieve(record_id, api_key, total_pages=0):
    """
    Checks the API status once and retrieves the result if completed.
    Does not poll. Returns content on success, status string if processing,
    or None on failure.
    """
    url = f"https://extraction-api.nanonets.com/files/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        if not result.get("success"):
            print(f"  ✗ API returned error: {result.get('detail', 'Unknown error')}")
            return None

        status = result.get("processing_status") or result.get("status")

        if status == "completed":
            print(f"  → Status: completed.")
            content = result.get("content", "")
            if not content:
                print(f"  ⚠ Warning: Content is empty in completed response.")
            return content
        elif status in ["processing", "failed"]:
            progress_info = ""
            if status == "processing" and total_pages > 0:
                pages_done = result.get("pages_processed", 0)
                proc_time = result.get("processing_time", 0.0)
                progress_info = f" (page {pages_done}/{total_pages} - {proc_time:.2f}s)"
            print(f"  → Status: {status}{progress_info}. Will check again later.")
            return status
        else:
            print(f"  ⚠ Unknown status: {status}")
            return status

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request error while checking status: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"  ✗ Error while checking status: {e}")
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
        print(f"  ✗ Request error for record_id {record_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                return e.response.json()
            except ValueError:
                return {"success": False, "detail": e.response.text}
        return None
    except Exception as e:
        print(f"  ✗ An unexpected error occurred for record_id {record_id}: {e}")
        return None

