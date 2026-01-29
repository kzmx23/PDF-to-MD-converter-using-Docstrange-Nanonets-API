import os
import re
import glob
import argparse
import shutil
from dotenv import load_dotenv
from .pdf_processor import analyze_pdf, calculate_chunks, split_pdf, parse_start_page_from_filename
from .converter import convert_file, get_file_status, upload_chunk, retrieve_chunk
from .renumberer import renumber_markdown_files, concatenate_markdown_files
from .djvu_converter import convert_djvu_to_pdf
from .accounts import get_api_key, get_account_count


def find_existing_chunks(base_name, output_dir):
    """
    Find existing chunk files in output directory based on lock files.
    Returns list of PDF file paths that have corresponding lock files.
    """
    # Pattern to match lock files: basename_pages_X_Y.pdf.lock
    lock_pattern = os.path.join(output_dir, f"{glob.escape(base_name)}_pages_*.pdf.lock")
    lock_files = glob.glob(lock_pattern)

    if not lock_files:
        return []

    # Extract PDF paths from lock files
    chunk_files = []
    for lock_file in sorted(lock_files):
        # Remove .lock extension to get PDF path
        pdf_path = lock_file[:-5]  # Remove ".lock"
        chunk_files.append(pdf_path)

    return chunk_files

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using DocStrange.")
    parser.add_argument("input_file", nargs='?', default=None, help="Path to the input PDF file (optional if using --file-status).")
    parser.add_argument("--output-dir", default="output", help="Directory to save output files.")
    parser.add_argument("--dry-run", action="store_true", help="Run without performing actual conversion or API calls.")
    parser.add_argument("--convert-only", action="store_true", help="Skip chunking logic and convert the file directly (for testing).")
    parser.add_argument("--retrieve-only", action="store_true", help="Force retrieval of a previously uploaded file by reading its record_id from a .lock file.")
    parser.add_argument("--file-status", help="Check the status of a single record_id or a comma-separated list of record_ids.")
    parser.add_argument("--account", type=int, default=1, help="Account ID to use for --file-status (1-4, default: 1).")
    parser.add_argument("--page-renumber", action="store_true", help="Renumbers the '## Page X' tags in output markdown files based on the filename.")
    parser.add_argument("--concat-mds", action="store_true", help="Concatenates renumbered markdown files into a single file.")
    parser.add_argument("--djvu-convert", action="store_true", help="Test DJVU to PDF conversion (converts input DJVU file to PDF without processing further).")
    parser.add_argument("--chunk-pages", help="Custom page range for chunking (e.g., '329-400'). Creates chunks for specified pages and uploads them.")
    parser.add_argument("--upload-missing", action="store_true", help="Find and upload chunk PDFs that have no lock file or MD file.")
    parser.add_argument("--fix-json-md", help="Fix MD files that contain JSON instead of markdown. Provide file path or 'all' to fix all in output-dir.")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Check if any accounts are configured
    if get_account_count() == 0:
        print("Error: No API accounts configured in .env file.")
        print("Please add API_KEY_1, API_KEY_2, etc. to your .env file.")
        return

    # Handle --file-status mode
    if args.file_status:
        try:
            api_key = get_api_key(args.account)
        except ValueError as e:
            print(f"Error: {e}")
            return

        record_ids = [rid.strip() for rid in args.file_status.split(',')]
        print(f"--- Checking status for {len(record_ids)} record(s) (using account {args.account}) ---")
        for rid in record_ids:
            print(f"\n--- Status for Record ID: {rid} ---")
            status_info = get_file_status(rid, api_key)
            if status_info and status_info.get("success"):
                status = status_info.get("processing_status") or status_info.get("status", "N/A")
                filename = status_info.get("filename", "N/A")
                pages = status_info.get("pages_processed", "N/A")
                proc_time = status_info.get("processing_time", "N/A")

                print(f"  Status:          {status}")
                print(f"  Filename:        {filename}")
                print(f"  Pages Processed: {pages}")
                print(f"  Processing Time: {proc_time}s")
            else:
                error_msg = status_info.get("detail", "File not found or invalid ID.") if status_info else "Request failed."
                print(f"  Error: {error_msg}")
        print("\n-------------------------------------------")
        return

    # Handle --page-renumber mode
    if args.page_renumber:
        if not args.input_file:
            parser.error("input_file is required when using --page-renumber.")
            return
        renumber_markdown_files(args.input_file, args.output_dir)
        return

    # Handle --concat-mds mode
    if args.concat_mds:
        if not args.input_file:
            parser.error("input_file is required when using --concat-mds.")
            return
        concatenate_markdown_files(args.input_file, args.output_dir)
        return

    # Handle --djvu-convert mode
    if args.djvu_convert:
        if not args.input_file:
            parser.error("input_file is required when using --djvu-convert.")
            return
        if not args.input_file.lower().endswith('.djvu'):
            print(f"Warning: Input file does not have .djvu extension: {args.input_file}")

        # Create output directory
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)

        # Determine output PDF path
        base_name = os.path.splitext(os.path.basename(args.input_file))[0]
        output_pdf_path = os.path.join(args.output_dir, f"{base_name}_converted.pdf")

        result = convert_djvu_to_pdf(args.input_file, output_pdf_path)
        if result:
            print(f"\n+ DJVU conversion test successful!")
            print(f"  Output: {result}")
        else:
            print(f"\nx DJVU conversion test failed.")
        return

    # Handle --upload-missing mode (find and upload chunks without lock/md files)
    if args.upload_missing:
        output_dir = args.output_dir
        if not os.path.exists(output_dir):
            print(f"Error: Output directory {output_dir} does not exist.")
            return

        # Find all chunk PDFs in output directory
        chunk_pattern = os.path.join(output_dir, "*_pages_*_*.pdf")
        all_chunks = glob.glob(chunk_pattern)

        if not all_chunks:
            print(f"No chunk files found in {output_dir}/")
            return

        # Filter to find those without lock file AND without md file
        missing_uploads = []
        for chunk_path in sorted(all_chunks):
            base_name = os.path.splitext(os.path.basename(chunk_path))[0]
            lock_file = os.path.join(output_dir, f"{base_name}.pdf.lock")
            md_file = os.path.join(output_dir, f"{base_name}.md")

            if not os.path.exists(lock_file) and not os.path.exists(md_file):
                missing_uploads.append(chunk_path)

        if not missing_uploads:
            print(f"All {len(all_chunks)} chunk files have lock files or MD files. Nothing to upload.")
            return

        print(f"Found {len(missing_uploads)} chunk(s) without lock or MD files (out of {len(all_chunks)} total):")
        for chunk_path in missing_uploads:
            print(f"  - {os.path.basename(chunk_path)}")

        print(f"\n{'='*25} UPLOAD PHASE {'='*24}")
        print(f"Starting upload of {len(missing_uploads)} file(s)...")
        print(f"Using {get_account_count()} API account(s) with failover")
        print(f"{'='*60}\n")

        for i, file_path in enumerate(missing_uploads, 1):
            print(f"[{i}/{len(missing_uploads)}] Uploading: {os.path.basename(file_path)}")
            upload_chunk(file_path, output_dir)
            print("-" * 30)

        print(f"\n{'='*60}")
        print(f"Upload of missing chunks complete!")
        print(f"{'='*60}")
        return

    # Handle --fix-json-md mode (convert JSON MD files to proper markdown)
    if args.fix_json_md:
        import json

        def extract_markdown_from_json(json_str):
            """Extract markdown content from a JSON string."""
            content_obj = json.loads(json_str)
            formats = content_obj.get("formats", {})
            markdown_data = formats.get("markdown", {})
            return markdown_data.get("content", "")

        def fix_json_md_file(file_path):
            """Convert a JSON-formatted MD file to proper markdown."""
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if content is JSON
                if not content.strip().startswith('{'):
                    print(f"  - {os.path.basename(file_path)}: Already in markdown format, skipping.")
                    return False

                # Try single JSON first
                try:
                    markdown_content = extract_markdown_from_json(content)
                except json.JSONDecodeError:
                    # File may contain multiple JSON objects (concatenated chunks)
                    # Split by common separators and process each part
                    markdown_parts = []

                    # Try splitting by "\n\n---\n\n" (concatenation separator)
                    parts = content.split("\n\n---\n\n")
                    if len(parts) == 1:
                        # Try splitting by "}\n{" pattern
                        parts = re.split(r'\}\s*\n\s*\{', content)
                        if len(parts) > 1:
                            # Restore braces
                            parts = [parts[0] + '}'] + ['{' + p + '}' for p in parts[1:-1]] + ['{' + parts[-1]]

                    for part in parts:
                        part = part.strip()
                        if part.startswith('{'):
                            try:
                                md = extract_markdown_from_json(part)
                                if md:
                                    markdown_parts.append(md)
                            except json.JSONDecodeError:
                                continue

                    if not markdown_parts:
                        print(f"  x {os.path.basename(file_path)}: Could not extract markdown from JSON.")
                        return False

                    markdown_content = "\n\n---\n\n".join(markdown_parts)

                if not markdown_content:
                    print(f"  - {os.path.basename(file_path)}: No markdown content found in JSON.")
                    return False

                # Write the extracted markdown back to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)

                print(f"  + {os.path.basename(file_path)}: Fixed successfully.")
                return True

            except Exception as e:
                print(f"  x {os.path.basename(file_path)}: Error - {e}")
                return False

        output_dir = args.output_dir
        fix_target = args.fix_json_md

        if fix_target.lower() == 'all':
            # Fix all MD files in output directory
            md_pattern = os.path.join(output_dir, "**", "*.md")
            md_files = glob.glob(md_pattern, recursive=True)

            if not md_files:
                print(f"No MD files found in {output_dir}/")
                return

            print(f"Scanning {len(md_files)} MD file(s) for JSON format...")
            fixed = 0
            for md_file in sorted(md_files):
                if fix_json_md_file(md_file):
                    fixed += 1

            print(f"\nFixed {fixed} file(s).")
        else:
            # Fix specific file
            if not os.path.exists(fix_target):
                print(f"Error: File {fix_target} not found.")
                return

            print(f"Fixing: {fix_target}")
            fix_json_md_file(fix_target)

        return

    # Handle --chunk-pages mode (custom chunking for specific page range)
    if args.chunk_pages:
        if not args.input_file:
            parser.error("input_file is required when using --chunk-pages.")
            return

        input_path = args.input_file
        if not os.path.exists(input_path):
            print(f"Error: File {input_path} not found.")
            return

        # Parse page range (e.g., "329-400")
        try:
            start_page, end_page = map(int, args.chunk_pages.split('-'))
            if start_page > end_page or start_page < 1:
                raise ValueError("Invalid range")
        except ValueError:
            print(f"Error: Invalid page range format. Use 'START-END' (e.g., '329-400').")
            return

        # Create output directory
        output_dir = args.output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Analyze the file to validate page range
        size_mb, num_pages = analyze_pdf(input_path)
        if end_page > num_pages:
            print(f"Error: End page {end_page} exceeds file's total pages ({num_pages}).")
            return

        print(f"Custom chunking mode: Pages {start_page}-{end_page} of {input_path}")
        print(f"Source file: {size_mb:.2f} MB, {num_pages} pages total")

        # Calculate chunks for the specified range
        range_pages = end_page - start_page + 1
        range_size_mb = size_mb * (range_pages / num_pages)  # Estimate size proportionally

        print(f"Range: {range_pages} pages, ~{range_size_mb:.2f} MB (estimated)")

        # Calculate chunks within the range (respecting 50MB/190 page limits)
        if range_size_mb > 50:
            avg_page_size_mb = range_size_mb / range_pages
            pages_per_40mb = int(40 / avg_page_size_mb)
            pages_per_chunk = max(1, min(pages_per_40mb, 190))
        elif range_pages > 190:
            pages_per_chunk = 190
        else:
            pages_per_chunk = range_pages

        chunks = []
        current_page = start_page
        while current_page <= end_page:
            chunk_end = min(current_page + pages_per_chunk - 1, end_page)
            chunks.append((current_page, chunk_end))
            current_page = chunk_end + 1

        print(f"Will create {len(chunks)} chunk(s):")
        for i, (s, e) in enumerate(chunks, 1):
            print(f"  Chunk {i}: Pages {s}-{e}")

        # Create the chunks
        print(f"\nSplitting file...")
        files_to_convert = split_pdf(input_path, chunks, output_dir)
        print(f"Created {len(files_to_convert)} chunk file(s)")

        # Upload the chunks
        print(f"\n{'='*25} UPLOAD PHASE {'='*24}")
        print(f"Starting upload of {len(files_to_convert)} file(s)...")
        print(f"Using {get_account_count()} API account(s) with failover")
        print(f"{'='*60}\n")

        for i, file_path in enumerate(files_to_convert, 1):
            print(f"[{i}/{len(files_to_convert)}] Uploading: {os.path.basename(file_path)}")
            upload_chunk(file_path, output_dir)
            print("-" * 30)

        print(f"\n{'='*60}")
        print(f"Custom chunking and upload complete!")
        print(f"Use --retrieve-only later to get the results.")
        print(f"{'='*60}")
        return

    # Ensure input_file is provided if not in status check mode
    if not args.input_file:
        parser.error("the following arguments are required: input_file")
        return

    input_path = args.input_file
    output_dir = args.output_dir

    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Auto-detect and convert DJVU files
    if input_path.lower().endswith('.djvu'):
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        converted_pdf_path = os.path.join(output_dir, f"{base_name}_converted.pdf")

        # Check if converted PDF already exists
        if os.path.exists(converted_pdf_path):
            print(f"Detected DJVU file. Converted PDF already exists: {os.path.basename(converted_pdf_path)}")
            print(f"Skipping DJVU to PDF conversion.\n")
            input_path = converted_pdf_path
        else:
            print(f"Detected DJVU file. Converting to PDF first...")
            result = convert_djvu_to_pdf(input_path, converted_pdf_path)
            if not result:
                print("Error: Failed to convert DJVU to PDF. Aborting.")
                return

            # Update input_path to use the converted PDF
            input_path = result
            print(f"Using converted PDF: {input_path}\n")

    # Handle --convert-only mode (skip chunking, convert directly)
    if args.convert_only:
        print(f"Convert-only mode: Converting {input_path} directly...")
        result = convert_file(input_path, output_dir)
        if result:
            print(f"Conversion successful!")
        else:
            print(f"Conversion failed.")
        return

    print(f"Processing {input_path}...")

    base_name = os.path.splitext(os.path.basename(input_path))[0]

    # Detect start page from filename (_from_XXX_page pattern)
    start_page = parse_start_page_from_filename(input_path)
    if start_page > 1:
        print(f"Detected start page from filename: {start_page}")

    # For --retrieve-only mode, find existing lock files instead of recalculating chunks
    if args.retrieve_only:
        files_to_convert = find_existing_chunks(base_name, output_dir)
        if not files_to_convert:
            print(f"No lock files found for '{base_name}' in {output_dir}/")
            print("Nothing to retrieve. Run without --retrieve-only to upload first.")
            return
        print(f"Found {len(files_to_convert)} existing chunk(s) with lock files")
    else:
        # 1. Analyze PDF
        try:
            size_mb, num_pages = analyze_pdf(input_path)
        except Exception as e:
            print(f"Error analyzing PDF: {e}")
            return

        print(f"File Size: {size_mb:.2f} MB")
        print(f"Page Count: {num_pages}")

        # Validate start_page
        if start_page > num_pages:
            print(f"Error: Start page {start_page} exceeds total pages ({num_pages}).")
            return

        if start_page > 1:
            effective_pages = num_pages - start_page + 1
            print(f"Processing pages {start_page}-{num_pages} ({effective_pages} pages)")

        # 2. Calculate Chunks (starting from detected start_page)
        chunks = calculate_chunks(size_mb, num_pages, start_page)

        if args.dry_run:
            print("\n--- Dry Run Plan ---")
            effective_pages = num_pages - start_page + 1
            effective_size = size_mb * (effective_pages / num_pages)
            if len(chunks) == 1 and chunks[0] == (start_page, num_pages) and effective_size <= 50 and effective_pages <= 200:
                 print("File is within limits. No splitting required.")
                 print(f"Plan: Convert {input_path} -> {os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0] + '.md')}")
            else:
                print("Splitting required:")
                for i, (start, end) in enumerate(chunks):
                    chunk_filename = f"{base_name}_pages_{start}_{end}.pdf"
                    print(f"  Chunk {i+1}: Pages {start}-{end} -> {chunk_filename}")
            print("--------------------")
            return

        # 3. Process
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        files_to_convert = []

        # Check if splitting is actually needed (single chunk within limits)
        effective_pages = num_pages - start_page + 1
        effective_size = size_mb * (effective_pages / num_pages)
        if len(chunks) == 1 and chunks[0] == (start_page, num_pages) and effective_size <= 50 and effective_pages <= 200:
            new_filename = f"{base_name}_pages_{start_page}_{num_pages}.pdf"
            new_path = os.path.join(output_dir, new_filename)

            if start_page > 1:
                # Need to extract pages from start_page to end
                print(f"Extracting pages {start_page}-{num_pages}...")
                files_to_convert = split_pdf(input_path, chunks, output_dir)
            else:
                # Copy file to output dir with new name
                shutil.copy(input_path, new_path)
                files_to_convert.append(new_path)

        else:
            print("Splitting file...")
            files_to_convert = split_pdf(input_path, chunks, output_dir)

    # 4. Upload Phase
    if not args.retrieve_only:
        print(f"\n{'='*25} UPLOAD PHASE {'='*24}")
        print(f"Starting upload of {len(files_to_convert)} file(s)...")
        print(f"Using {get_account_count()} API account(s) with failover")
        print(f"{'='*60}\n")
        for i, file_path in enumerate(files_to_convert, 1):
            print(f"[{i}/{len(files_to_convert)}] Uploading: {os.path.basename(file_path)}")
            upload_chunk(file_path, output_dir)
            print("-" * 30)
    else:
        print(f"\n{'='*25} UPLOAD PHASE SKIPPED {'='*24}")


    # 5. Retrieval Phase
    print(f"\n{'='*24} RETRIEVAL PHASE {'='*23}")
    print(f"Starting retrieval of {len(files_to_convert)} file(s)...")
    print(f"{'='*60}\n")

    successful = 0
    failed = 0
    processing_count = 0

    for i, file_path in enumerate(files_to_convert, 1):
        print(f"[{i}/{len(files_to_convert)}] Checking: {os.path.basename(file_path)}")
        result = retrieve_chunk(file_path, output_dir)

        if result == "processing":
            processing_count += 1
        elif result == "failed":
            failed += 1
        elif result is None:
            failed += 1
            # Error message is already printed by retrieve_chunk
        else:
            successful += 1
            print(f"+ Success\n")

    print(f"{'='*60}")
    print(f"Retrieval complete!")
    print(f"  - Successful: {successful}/{len(files_to_convert)}")
    print(f"  - Still Processing: {processing_count}/{len(files_to_convert)}")
    if failed > 0:
        print(f"  - Failed: {failed}/{len(files_to_convert)}")
    print(f"{'='*60}")

    if processing_count > 0 and successful == 0 and failed == 0:
        print("\nAll files are still processing. Please run the command again with the --retrieve-only flag later.")
    elif processing_count > 0:
        print(f"\n{processing_count} file(s) are still processing. Run the command again with the --retrieve-only flag to get the remaining files.")


if __name__ == "__main__":
    main()
