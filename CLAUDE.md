# Claude Code Project Guide

## Project Overview

This is a PDF/DJVU to Markdown converter using the NanoNets API. It handles large files by chunking, supports multi-account failover, and includes an automated daemon for batch processing.

## Architecture

```
app/
├── main.py           # CLI entry point, argument parsing, orchestration
├── pdf_processor.py  # PDF analysis, chunking, splitting
├── converter.py      # NanoNets API communication (upload/retrieve)
├── accounts.py       # Multi-account management, lock file parsing
├── renumberer.py     # Page renumbering, validation, concatenation
├── djvu_converter.py # DJVU to PDF conversion (uses ddjvu)
└── daemon.py         # Automated batch processing daemon
```

## Key Data Flows

### Standard Processing Pipeline
```
Input PDF/DJVU → analyze_pdf() → calculate_chunks() → split_pdf()
    → upload_chunk() [creates .lock file] → retrieve_chunk() [creates .md, removes .lock]
    → renumber_markdown_files() → concatenate_markdown_files()
```

### Daemon Workflow
```
1. process_pending_retrievals()  - Check status of files with .lock files
2. process_finished_conversions() - Concatenate files where all .md exist
3. process_new_files()           - Start processing new input files
```

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Chunk PDF | `{base}_pages_{start}_{end}.pdf` | `book_pages_1_190.pdf` |
| Lock file | `{base}_pages_{start}_{end}.pdf.lock` | `book_pages_1_190.pdf.lock` |
| Chunk MD | `{base}_pages_{start}_{end}.md` | `book_pages_1_190.md` |
| Concatenated | `{base}_concat_pages_{start}_{end}.md` | `book_concat_pages_1_500.md` |
| Converted DJVU | `{base}_converted.pdf` | `sample_converted.pdf` |

## Special Filename Pattern: `_from_XXX_page`

Files with `_from_XXX_page` in the filename skip pages 1 to XXX-1:
- `book_from_100_page.pdf` (300 pages) → processes pages 100-300
- Chunks: `book_from_100_page_pages_100_289.pdf`, etc.
- Concatenated: `book_from_100_page_concat_pages_100_300.md`

Parsing function: `pdf_processor.parse_start_page_from_filename()`

## API Limits & Chunking Rules

- **Max file size**: 50 MB per chunk
- **Max pages**: 200 pages per chunk (uses 190 for safety margin)
- **Chunking logic** in `calculate_chunks()`:
  - If file > 50MB: calculate pages per 40MB chunk
  - If pages > 200: use 190 pages per chunk
  - Otherwise: single chunk

## Lock File Format

Lock files store `account_id:record_id` to track which API account uploaded each chunk:
```
3:1763488
```

Parsing: `accounts.parse_lock_file(content)`

## Multi-Account Failover

- Accounts configured in `.env`: `API_KEY_1`, `API_KEY_2`, etc. (up to 4)
- Upload tries accounts in order until success
- Rate limit (429) or access error (403) triggers failover to next account
- Lock file records which account was used for later retrieval

## Key Functions Reference

### pdf_processor.py
- `parse_start_page_from_filename(path)` - Extract start page from `_from_XXX_page` pattern
- `analyze_pdf(path)` - Returns `(size_mb, num_pages)`
- `calculate_chunks(size_mb, num_pages, start_page=1)` - Returns `[(start, end), ...]`
- `split_pdf(path, chunks, output_dir)` - Creates chunk PDFs, returns paths

### converter.py
- `upload_chunk(file_path, output_dir)` - Upload to API, create lock file
- `retrieve_chunk(file_path, output_dir)` - Check status, download MD if ready
- `upload_file(file_path, api_key)` - Low-level API upload with retry
- `check_status_and_retrieve(record_id, api_key)` - Low-level API status check

### renumberer.py
- `renumber_markdown_files(base_path, output_dir)` - Fix `## Page X` markers
- `validate_chunks_for_concatenation(base_name, output_dir)` - Check all chunks ready
- `concatenate_markdown_files(base_path, output_dir)` - Merge all MDs into one

### daemon.py
- `find_input_files()` - Find PDF/DJVU in input folder
- `has_lock_files(source_file)` - Check if processing in progress
- `is_conversion_finished(source_file)` - Check if all MDs exist
- `run_conversion/retrieval/concatenation(source_file)` - Subprocess execution

## CLI Flags

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview chunking plan without processing |
| `--retrieve-only` | Only check/download results, no uploads |
| `--page-renumber` | Fix page numbers in existing MD files |
| `--concat-mds` | Concatenate all chunk MDs into one |
| `--file-status=ID` | Check API status for record ID |
| `--chunk-pages=X-Y` | Process specific page range |
| `--upload-missing` | Upload chunks without lock/MD files |
| `--djvu-convert` | Test DJVU conversion only |

## Folder Structure

- `input/` - Drop files here for daemon processing
- `output/` - Chunk PDFs, MDs, lock files during processing
- `output/done/` - Completed files moved here by daemon

## Common Tasks

### Add new CLI flag
1. Add to `argparse` in `main.py`
2. Handle in appropriate section of `main()`

### Modify chunking logic
1. Edit `calculate_chunks()` in `pdf_processor.py`
2. Consider `split_pdf()` if extraction logic changes

### Change API behavior
1. Edit `converter.py` for upload/retrieve logic
2. Edit `accounts.py` for multi-account handling

### Modify daemon behavior
1. Edit `daemon.py` processing functions
2. Consider `is_conversion_finished()` for completion detection
