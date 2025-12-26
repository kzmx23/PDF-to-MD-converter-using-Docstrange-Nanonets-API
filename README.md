# PDF/DJVU to Markdown Converter

A Python application that converts PDF and DJVU files to Markdown format using the NanoNets API. The app is designed to handle large files by splitting them into manageable chunks and includes features for resuming interrupted jobs, post-processing, and automated batch processing.

## Core Features

-   **PDF & DJVU to Markdown Conversion**: Utilizes the NanoNets async API to convert PDF and DJVU content to Markdown.
-   **DJVU Support**: Automatically detects and converts DJVU files to PDF before processing. Smart caching avoids redundant conversions.
-   **Automatic File Splitting**: Handles PDF files that exceed the API's limits (50MB size or 200 pages) by automatically splitting them into valid chunks.
-   **Multi-Account Failover**: Configure up to 4 NanoNets API accounts for automatic failover when rate limits are exceeded. Different chunks can use different accounts.
-   **Resumable Processing**: Creates `.lock` files for uploaded chunks (storing account_id:record_id), allowing the conversion to be resumed if interrupted. The `--retrieve-only` flag forces the app to only check for results of already-uploaded files.
-   **Smart Retry Logic**: Automatically retries transient errors (SSL, connection timeouts, 5xx server errors) up to 3 times before failing over to the next account.
-   **Page Renumbering**: Fixes page numbering in the final Markdown files. The API generates each chunk starting from "Page 1," and the `--page-renumber` tool corrects this to reflect the original document's pagination.
-   **File Concatenation**: The `--concat-mds` tool merges the individual, renumbered Markdown chunks into a single, complete document.
-   **Status Checking**: The `--file-status` utility allows you to check the processing status of one or more jobs using their `record_id`.
-   **Automated Daemon Mode**: Background daemon for continuous monitoring and processing of files from an input folder.

## Project Structure

The project is organized into an application package (`app`) and a test suite (`test`).

```
nanonets_pdf_ocr/
├── app/
│   ├── __init__.py          # Makes 'app' a Python package
│   ├── main.py              # Main entry point, handles CLI arguments
│   ├── pdf_processor.py     # PDF analysis and splitting logic
│   ├── converter.py         # Handles all communication with the NanoNets API
│   ├── accounts.py          # Multi-account management and failover logic
│   ├── renumberer.py        # Contains logic for renumbering and concatenating MD files
│   ├── djvu_converter.py    # DJVU to PDF conversion using ddjvu
│   └── daemon.py            # Automated daemon for batch processing
├── test/                    # Test files (ignored by git)
├── input/                   # Input folder for daemon mode
├── output/                  # Default directory for all output files (ignored by git)
│   └── done/                # Completed conversions moved here by daemon
├── .gitignore               # Specifies files and directories to be ignored by git
├── .env-example             # Example environment file
├── README.md                # This file
└── requirements.txt         # Python dependencies
```

## Installation

1.  **Clone the repository**
    ```bash
    git clone <repository_url>
    cd nanonets_pdf_ocr
    ```

2.  **Set up a virtual environment** (recommended)
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install DJVU support** (required for DJVU file conversion)
    ```bash
    # Ubuntu/Debian
    sudo apt-get install djvulibre-bin

    # macOS
    brew install djvulibre

    # Arch Linux
    sudo pacman -S djvulibre
    ```

5.  **Create your environment file**
    Copy the example file and configure your API accounts.
    ```bash
    cp .env-example .env
    # Now edit .env and add your API keys
    ```

    The application supports up to 4 NanoNets API accounts for automatic failover:
    ```bash
    # .env file format
    API_KEY_1=your_first_api_key_here
    API_KEY_2=your_second_api_key_here   # Optional
    API_KEY_3=your_third_api_key_here    # Optional
    API_KEY_4=your_fourth_api_key_here   # Optional
    ```

    **Failover Behavior:**
    - When uploading chunks, the app tries accounts in order (1→2→3→4)
    - If an account hits rate limit (429) or access error (403), it automatically tries the next account
    - Each chunk's lock file stores which account was used: `account_id:record_id`
    - When retrieving results, the app uses the correct account based on the lock file
    - You only need to configure API_KEY_1 minimum; additional accounts are optional but recommended for high-volume processing

## Usage

Because the main script is inside a package, you should run it as a module from the project's root directory.

### Basic Command Structure

```bash
python3 -m app <input_file> [options]
```

### Command-Line Arguments & Tools

The application has two main modes: **Conversion** and **Post-processing/Utility**.

#### Conversion Workflow

This is the default mode. It takes a PDF or DJVU file, splits it if necessary, and converts it to Markdown.

-   `input_file`: (Required for conversion) The path to the PDF or DJVU file you want to convert.
-   `--output-dir <dir>`: Directory to save all output files (default: `output`).
-   `--dry-run`: Preview the splitting plan without processing any files.
-   `--retrieve-only`: Skips the upload step and only tries to retrieve results for files that have an existing `.lock` file in the output directory.

**Example: Convert a large PDF**
```bash
python3 -m app "test/том 1 книга 3.pdf"
```

**Example: Convert a DJVU file**
DJVU files are automatically detected and converted to PDF before processing:
```bash
python3 -m app "test/sample1.djvu"
```

**Example: Resume an interrupted job**
If the process was stopped, some `.lock` files may exist in `output/`. Running the same command again will automatically resume from where it left off. To *only* perform retrieval without attempting new uploads, use:
```bash
python3 -m app "test/том 1 книга 3.pdf" --retrieve-only
```

---

#### Post-processing & Utility Tools

These tools work on already generated files or use record IDs.

-   `--file-status <id1,id2,...>`: Checks the status of one or more comma-separated `record_id`s. Does not require an `input_file`.
    ```bash
    python3 -m app --file-status=111111,222222
    ```

    Use `--account <N>` to specify which API account to use for status checks (default: account 1):
    ```bash
    python3 -m app --file-status=111111 --account=2
    ```

-   `--page-renumber`: Corrects the `## Page X` tags in the generated Markdown files. Requires `input_file` to identify the set of files to process.
    ```bash
    python3 -m app "test/том 1 книга 3.pdf" --page-renumber
    ```

-   `--concat-mds`: Validates all chunks are complete, runs the renumbering process, then merges all the Markdown chunks into a single file named `<basename>_concat_pages_1_NNN.md`. Requires `input_file`.

    **Validation checks performed before concatenation:**
    - No `.lock` files exist (all chunks finished processing)
    - All PDF chunks have corresponding `.md` files
    - Page ranges are continuous with no gaps (1→N)

    If validation fails, concatenation is aborted with an error message.
    ```bash
    python3 -m app "test/том 1 книга 3.pdf" --concat-mds
    ```

-   `--djvu-convert`: Test DJVU to PDF conversion without processing further. Useful for testing DJVU conversion independently.
    ```bash
    python3 -m app "test/sample1.djvu" --djvu-convert
    ```

-   `--chunk-pages <START-END>`: Create chunks for a specific page range and upload them. Useful for processing missing pages or re-processing specific sections.
    ```bash
    # Create chunks for pages 329-400 and upload them
    python3 -m app "path/to/file.pdf" --chunk-pages=329-400
    ```
    The algorithm respects API limits (max 50MB, max 190 pages per chunk) and will split the range into multiple chunks if needed.

-   `--upload-missing`: Scan the output directory for chunk PDF files that don't have a corresponding lock file or MD file, and upload them.
    ```bash
    # Find and upload any chunks that weren't processed
    python3 -m app --upload-missing
    ```

---

## Automated Daemon Mode

The daemon module provides automated batch processing by monitoring an input folder for new files.

### Features

-   **Continuous Monitoring**: Checks `input/` folder for PDF/DJVU files
-   **Multi-Account Failover**: Automatically uses all configured API accounts with failover
-   **Active Retrieval**: Automatically checks processing status and downloads completed results from the cloud
-   **Automatic Processing**: Starts conversion workflow for new files
-   **Completion Detection**: Identifies finished conversions (no lock files + all MD files exist)
-   **Auto-Concatenation**: Automatically creates concatenated markdown files for completed conversions
-   **File Management**: Moves source files and outputs to `output/done/` when complete
-   **Comprehensive Logging**: All operations logged with timestamps to `/var/log/ds_nnt_pdf2md.log`
-   **Instance Protection**: Prevents multiple daemon instances using lock file

### Workflow

1. Check `input/` folder for PDF/DJVU files
2. **Active Retrieval Phase**: For files with lock files (being processed):
   - Run `--retrieve-only` to check processing status
   - Download completed MD files from the cloud
   - Remove lock files for completed chunks
3. **Completion Detection**: Check for finished conversions:
   - No `.lock` files exist for any chunks
   - All chunks have corresponding `.md` files
4. **Finalization Phase**: For finished conversions:
   - Run concatenation to create `{name}_concat_pages_X_Y.md`
   - Move source file to `output/done/`
   - Move all chunks, MD files, and concatenated file to `output/done/`
5. **New Files Phase**: Start conversion for new files (no existing chunks in output/)

### Manual Execution

```bash
python3 -m app.daemon
```

### Setup with Cron

To run the daemon every 5 minutes, add this to your crontab:

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths to match your installation):
*/5 * * * * cd /home/max/code/nanonets_pdf_ocr && /home/max/code/nanonets_pdf_ocr/venv/bin/python3 -m app.daemon
```

**Alternative with explicit logging:**
```bash
*/5 * * * * cd /path/to/project && /path/to/venv/bin/python3 -m app.daemon >> /path/to/project/daemon.log 2>&1
```

### Usage Pattern

1. Place PDF/DJVU files in the `input/` folder
2. Daemon automatically processes them every 5 minutes
3. Monitor progress in the log file
4. Completed files appear in `output/done/` with concatenated markdown

### Log File

The daemon writes detailed logs to `/var/log/ds_nnt_pdf2md.log` (or `daemon.log` in project root if no write permission).

Log entries include:
- Daemon start/finish timestamps
- Files detected and processed
- Conversion workflow output
- File movement operations
- Any errors encountered

## Testing

To run the test suite, execute Pytest from the project root:

```bash
pytest
```

For more detailed output:
```bash
pytest -v -s
```