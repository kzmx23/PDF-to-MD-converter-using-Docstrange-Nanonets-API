# PDF to Markdown Converter

A Python application that converts PDF files to Markdown format using the NanoNets API. The app is designed to handle large files by splitting them into manageable chunks and includes features for resuming interrupted jobs and post-processing the output.

## Core Features

-   **PDF to Markdown Conversion**: Utilizes the NanoNets async API to convert PDF content to Markdown.
-   **Automatic File Splitting**: Handles PDF files that exceed the API's limits (50MB size or 200 pages) by automatically splitting them into valid chunks.
-   **Resumable Processing**: Creates `.lock` files for uploaded chunks, allowing the conversion to be resumed if interrupted. The `--retrieve-only` flag forces the app to only check for results of already-uploaded files.
-   **Page Renumbering**: Fixes page numbering in the final Markdown files. The API generates each chunk starting from "Page 1," and the `--page-renumber` tool corrects this to reflect the original document's pagination.
-   **File Concatenation**: The `--concat-mds` tool merges the individual, renumbered Markdown chunks into a single, complete document.
-   **Status Checking**: The `--file-status` utility allows you to check the processing status of one or more jobs using their `record_id`.

## Project Structure

The project is organized into an application package (`app`) and a test suite (`test`).

```
nanonets_pdf_ocr/
├── app/
│   ├── __init__.py          # Makes 'app' a Python package
│   ├── main.py              # Main entry point, handles CLI arguments
│   ├── pdf_processor.py     # PDF analysis and splitting logic
│   ├── converter.py         # Handles all communication with the NanoNets API
│   └── renumberer.py        # Contains logic for renumbering and concatenating MD files
├── test/
│   ├── test_app.py          # Pytest test suite
│   ├── test_book.pdf        # Test files...
│   └── ...
├── output/                  # Default directory for all output files (ignored by git)
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

4.  **Create your environment file**
    Copy the example file and add your API key.
    ```bash
    cp .env-example .env
    # Now edit .env and add your key
    # API_KEY=your_nanonets_api_key_here
    ```

## Usage

Because the main script is inside a package, you should run it as a module from the project's root directory.

### Basic Command Structure

```bash
python3 -m app <input_file> [options]
```

### Command-Line Arguments & Tools

The application has two main modes: **Conversion** and **Post-processing/Utility**.

#### Conversion Workflow

This is the default mode. It takes a PDF file, splits it if necessary, and converts it to Markdown.

-   `input_file`: (Required for conversion) The path to the PDF file you want to convert.
-   `--output-dir <dir>`: Directory to save all output files (default: `output`).
-   `--dry-run`: Preview the splitting plan without processing any files.
-   `--retrieve-only`: Skips the upload step and only tries to retrieve results for files that have an existing `.lock` file in the output directory.

**Example: Convert a large PDF**
```bash
python3 -m app "test/том 1 книга 3.pdf"
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

-   `--page-renumber`: Corrects the `## Page X` tags in the generated Markdown files. Requires `input_file` to identify the set of files to process.
    ```bash
    python3 -m app "test/том 1 книга 3.pdf" --page-renumber
    ```

-   `--concat-mds`: First runs the renumbering process, then merges all the Markdown chunks into a single file named `<basename>_concat_pages_1_NNN.md`. Requires `input_file`.
    ```bash
    python3 -m app "test/том 1 книга 3.pdf" --concat-mds
    ```

## Testing

To run the test suite, execute Pytest from the project root:

```bash
pytest
```

For more detailed output:
```bash
pytest -v -s
```