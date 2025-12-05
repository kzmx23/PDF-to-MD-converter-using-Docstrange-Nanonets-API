#!/usr/bin/env python3
"""
Daemon module for automatic PDF/DJVU to Markdown conversion.
Runs periodically to process files from input folder.
"""

import os
import sys
import glob
import shutil
import subprocess
import fcntl
import re
from datetime import datetime
from pathlib import Path

# Configuration
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
DONE_FOLDER = os.path.join(OUTPUT_FOLDER, "done")
LOG_FILE = "/var/log/ds_nnt_pdf2md.log"
LOCK_FILE = "/tmp/ds_nnt_pdf2md.lock"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)


class DaemonLock:
    """Context manager for daemon lock file to prevent multiple instances."""

    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_fd = None

    def __enter__(self):
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            return self
        except IOError:
            log_message("Another instance is already running. Exiting.")
            sys.exit(0)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_fd:
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
            self.lock_fd.close()
            try:
                os.remove(self.lock_file)
            except OSError:
                pass


def log_message(message, include_timestamp=True):
    """Write a message to the log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n" if include_timestamp else f"{message}\n"

    try:
        # Try to write to the log file
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry)
    except PermissionError:
        # Fallback to local log file if no permission for /var/log
        local_log = os.path.join(PROJECT_ROOT, "daemon.log")
        with open(local_log, 'a') as f:
            f.write(log_entry)
        # Also print to stdout
        print(log_entry.strip())


def ensure_folders_exist():
    """Ensure required folders exist."""
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(DONE_FOLDER, exist_ok=True)


def find_input_files():
    """Find all PDF and DJVU files in the input folder."""
    pdf_files = glob.glob(os.path.join(INPUT_FOLDER, "*.pdf"))
    djvu_files = glob.glob(os.path.join(INPUT_FOLDER, "*.djvu"))
    return pdf_files + djvu_files


def get_base_name(file_path):
    """Get base name without extension."""
    return os.path.splitext(os.path.basename(file_path))[0]


def has_lock_files(source_file):
    """
    Check if a source file has any lock files (indicating processing in progress).
    Returns True if lock files exist.
    """
    base_name = get_base_name(source_file)

    # For DJVU files, the converted PDF name is different
    if source_file.lower().endswith('.djvu'):
        base_name = f"{base_name}_converted"

    # Find all related lock files in output folder
    lock_pattern = os.path.join(OUTPUT_FOLDER, f"{base_name}_pages_*.pdf.lock")
    lock_files = glob.glob(lock_pattern)

    return len(lock_files) > 0


def is_conversion_finished(source_file):
    """
    Check if conversion is finished for a source file.
    Returns True if:
    1. No .lock files exist for any chunks
    2. All chunks have corresponding .md files
    """
    base_name = get_base_name(source_file)

    # For DJVU files, the converted PDF name is different
    if source_file.lower().endswith('.djvu'):
        base_name = f"{base_name}_converted"

    # Find all related chunk PDF files in output folder
    chunk_pattern = os.path.join(OUTPUT_FOLDER, f"{base_name}_pages_*.pdf")
    chunk_files = glob.glob(chunk_pattern)

    if not chunk_files:
        # No chunks found, conversion hasn't started or file was already processed
        return False

    # Check for lock files
    for chunk_file in chunk_files:
        lock_file = f"{chunk_file}.lock"
        if os.path.exists(lock_file):
            return False

    # Check if all chunks have corresponding .md files
    for chunk_file in chunk_files:
        md_file = chunk_file.replace('.pdf', '.md')
        if not os.path.exists(md_file):
            return False

    return True


def run_conversion(source_file):
    """
    Run the conversion workflow for a source file.
    Returns True if conversion was initiated successfully.
    """
    log_message(f"Starting conversion for: {os.path.basename(source_file)}")

    try:
        # Change to project root directory
        os.chdir(PROJECT_ROOT)

        # Run the app
        cmd = [
            sys.executable, "-m", "app",
            source_file,
            "--output-dir", OUTPUT_FOLDER
        ]

        log_message(f"  Command: {' '.join(cmd)}")

        # Run and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        # Log the output
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    log_message(f"  [APP] {line}", include_timestamp=False)

        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    log_message(f"  [ERR] {line}", include_timestamp=False)

        if result.returncode == 0:
            log_message(f"  Conversion initiated successfully")
            return True
        else:
            log_message(f"  Conversion failed with exit code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        log_message(f"  ERROR: Conversion timed out after 1 hour")
        return False
    except Exception as e:
        log_message(f"  ERROR: {str(e)}")
        return False


def run_retrieval(source_file):
    """
    Run the retrieval workflow for a file that's being processed.
    Uses --retrieve-only flag to check status and download completed files.
    Returns True if retrieval was run successfully (regardless of completion status).
    """
    log_message(f"Retrieving results for: {os.path.basename(source_file)}")

    try:
        # Change to project root directory
        os.chdir(PROJECT_ROOT)

        # Run the app with --retrieve-only
        cmd = [
            sys.executable, "-m", "app",
            source_file,
            "--output-dir", OUTPUT_FOLDER,
            "--retrieve-only"
        ]

        log_message(f"  Command: {' '.join(cmd)}")

        # Run and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Log the output
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    log_message(f"  [APP] {line}", include_timestamp=False)

        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    log_message(f"  [ERR] {line}", include_timestamp=False)

        if result.returncode == 0:
            log_message(f"  Retrieval check completed")
            return True
        else:
            log_message(f"  Retrieval check failed with exit code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        log_message(f"  ERROR: Retrieval timed out")
        return False
    except Exception as e:
        log_message(f"  ERROR: {str(e)}")
        return False


def run_concatenation(source_file):
    """
    Run the concatenation workflow for a finished conversion.
    Returns True if successful.
    """
    log_message(f"Running concatenation for: {os.path.basename(source_file)}")

    try:
        # Change to project root directory
        os.chdir(PROJECT_ROOT)

        # Run the app with --concat-mds
        cmd = [
            sys.executable, "-m", "app",
            source_file,
            "--output-dir", OUTPUT_FOLDER,
            "--concat-mds"
        ]

        log_message(f"  Command: {' '.join(cmd)}")

        # Run and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Log the output
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    log_message(f"  [APP] {line}", include_timestamp=False)

        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    log_message(f"  [ERR] {line}", include_timestamp=False)

        if result.returncode == 0:
            log_message(f"  Concatenation completed successfully")
            return True
        else:
            log_message(f"  Concatenation failed with exit code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        log_message(f"  ERROR: Concatenation timed out")
        return False
    except Exception as e:
        log_message(f"  ERROR: {str(e)}")
        return False


def move_completed_files(source_file):
    """
    Move source file and all related output files to done folder.
    """
    base_name = get_base_name(source_file)
    log_message(f"Moving completed files for: {os.path.basename(source_file)}")

    try:
        # Move source file to done folder
        source_dest = os.path.join(DONE_FOLDER, os.path.basename(source_file))
        shutil.move(source_file, source_dest)
        log_message(f"  Moved: {os.path.basename(source_file)} -> done/")

        # For DJVU files, also move the converted PDF
        if source_file.lower().endswith('.djvu'):
            converted_pdf = os.path.join(OUTPUT_FOLDER, f"{base_name}_converted.pdf")
            if os.path.exists(converted_pdf):
                pdf_dest = os.path.join(DONE_FOLDER, os.path.basename(converted_pdf))
                shutil.move(converted_pdf, pdf_dest)
                log_message(f"  Moved: {os.path.basename(converted_pdf)} -> done/")
            base_name = f"{base_name}_converted"

        # Find and move all chunk PDFs and MDs
        chunk_pattern = os.path.join(OUTPUT_FOLDER, f"{base_name}_pages_*.pdf")
        chunk_files = glob.glob(chunk_pattern)

        for chunk_file in chunk_files:
            # Move chunk PDF
            chunk_dest = os.path.join(DONE_FOLDER, os.path.basename(chunk_file))
            if os.path.exists(chunk_file):
                shutil.move(chunk_file, chunk_dest)
                log_message(f"  Moved: {os.path.basename(chunk_file)} -> done/")

            # Move corresponding MD file
            md_file = chunk_file.replace('.pdf', '.md')
            if os.path.exists(md_file):
                md_dest = os.path.join(DONE_FOLDER, os.path.basename(md_file))
                shutil.move(md_file, md_dest)
                log_message(f"  Moved: {os.path.basename(md_file)} -> done/")

        # Move concatenated file
        concat_pattern = os.path.join(OUTPUT_FOLDER, f"{base_name}_concat_*.md")
        concat_files = glob.glob(concat_pattern)
        for concat_file in concat_files:
            concat_dest = os.path.join(DONE_FOLDER, os.path.basename(concat_file))
            shutil.move(concat_file, concat_dest)
            log_message(f"  Moved: {os.path.basename(concat_file)} -> done/")

        log_message(f"  All files moved successfully")
        return True

    except Exception as e:
        log_message(f"  ERROR moving files: {str(e)}")
        return False


def process_finished_conversions():
    """
    Check for finished conversions and process them.
    """
    input_files = find_input_files()

    for source_file in input_files:
        if is_conversion_finished(source_file):
            log_message(f"Detected finished conversion: {os.path.basename(source_file)}")

            # Run concatenation
            if run_concatenation(source_file):
                # Move all files to done folder
                move_completed_files(source_file)


def process_new_files():
    """
    Find and process new files in input folder.
    """
    input_files = find_input_files()

    if not input_files:
        return

    for source_file in input_files:
        base_name = get_base_name(source_file)

        # For DJVU files, check for converted PDF
        if source_file.lower().endswith('.djvu'):
            search_base = f"{base_name}_converted"
        else:
            search_base = base_name

        # Check if any chunks exist in output folder (conversion already started)
        chunk_pattern = os.path.join(OUTPUT_FOLDER, f"{search_base}_pages_*.pdf")
        existing_chunks = glob.glob(chunk_pattern)

        if not existing_chunks:
            # No chunks exist, this is a new file
            log_message(f"Found new file: {os.path.basename(source_file)}")
            run_conversion(source_file)


def process_pending_retrievals():
    """
    Check for files with lock files and run retrieval to check if processing is complete.
    This actively retrieves results for files currently being processed in the cloud.
    """
    input_files = find_input_files()

    for source_file in input_files:
        # Check if file has lock files (indicating it's being processed)
        if has_lock_files(source_file):
            log_message(f"Found file with lock files: {os.path.basename(source_file)}")
            # Run retrieval to check status and download if ready
            run_retrieval(source_file)


def main():
    """Main daemon entry point."""
    log_message("=" * 60)
    log_message("Daemon started")

    # Use lock to prevent multiple instances
    with DaemonLock(LOCK_FILE):
        try:
            # Ensure folders exist
            ensure_folders_exist()

            # Check input folder
            input_files = find_input_files()

            if not input_files:
                log_message("No PDF or DJVU files found in input folder")
                log_message("Daemon finished")
                return

            log_message(f"Found {len(input_files)} file(s) in input folder")

            # First, try to retrieve results for files being processed
            process_pending_retrievals()

            # Then, check for finished conversions and concatenate
            process_finished_conversions()

            # Finally, process new files
            process_new_files()

            log_message("Daemon finished")

        except Exception as e:
            log_message(f"ERROR: Unexpected error: {str(e)}")
            import traceback
            log_message(traceback.format_exc())


if __name__ == "__main__":
    main()
