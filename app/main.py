import os
import argparse
import shutil
from dotenv import load_dotenv
from .pdf_processor import analyze_pdf, calculate_chunks, split_pdf
from .converter import convert_file, get_file_status, upload_chunk, retrieve_chunk
from .renumberer import renumber_markdown_files, concatenate_markdown_files

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using DocStrange.")
    parser.add_argument("input_file", nargs='?', default=None, help="Path to the input PDF file (optional if using --file-status).")
    parser.add_argument("--output-dir", default="output", help="Directory to save output files.")
    parser.add_argument("--dry-run", action="store_true", help="Run without performing actual conversion or API calls.")
    parser.add_argument("--convert-only", action="store_true", help="Skip chunking logic and convert the file directly (for testing).")
    parser.add_argument("--retrieve-only", action="store_true", help="Force retrieval of a previously uploaded file by reading its record_id from a .lock file.")
    parser.add_argument("--file-status", help="Check the status of a single record_id or a comma-separated list of record_ids.")
    parser.add_argument("--page-renumber", action="store_true", help="Renumbers the '## Page X' tags in output markdown files based on the filename.")
    parser.add_argument("--concat-mds", action="store_true", help="Concatenates renumbered markdown files into a single file.")

    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        print("Error: API_KEY not found in .env file.")
        return

    # Handle --file-status mode
    if args.file_status:
        record_ids = [rid.strip() for rid in args.file_status.split(',')]
        print(f"--- Checking status for {len(record_ids)} record(s) ---")
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

    # Handle --convert-only mode (skip chunking, convert directly)
    if args.convert_only:
        print(f"Convert-only mode: Converting {input_path} directly...")
        result = convert_file(input_path, output_dir, api_key)
        if result:
            print(f"Conversion successful!")
        else:
            print(f"Conversion failed.")
        return

    print(f"Processing {input_path}...")

    # 1. Analyze PDF
    try:
        size_mb, num_pages = analyze_pdf(input_path)
    except Exception as e:
        print(f"Error analyzing PDF: {e}")
        return

    print(f"File Size: {size_mb:.2f} MB")
    print(f"Page Count: {num_pages}")
    
    # 2. Calculate Chunks
    chunks = calculate_chunks(size_mb, num_pages)
    
    if args.dry_run:
        print("\n--- Dry Run Plan ---")
        if len(chunks) == 1 and chunks[0] == (1, num_pages) and size_mb <= 50 and num_pages <= 200:
             print("File is within limits. No splitting required.")
             print(f"Plan: Convert {input_path} -> {os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0] + '.md')}")
        else:
            print("Splitting required:")
            for i, (start, end) in enumerate(chunks):
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                chunk_filename = f"{base_name}_pages_{start}_{end}.pdf"
                print(f"  Chunk {i+1}: Pages {start}-{end} -> {chunk_filename}")
        print("--------------------")
        return

    # 3. Process
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    files_to_convert = []
    
    # Check if splitting is actually needed
    if len(chunks) == 1 and chunks[0] == (1, num_pages) and size_mb <= 50 and num_pages <= 200:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        new_filename = f"{base_name}_pages_1_{num_pages}.pdf"
        new_path = os.path.join(output_dir, new_filename)
        
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
        print(f"{'='*60}\n")
        for i, file_path in enumerate(files_to_convert, 1):
            print(f"[{i}/{len(files_to_convert)}] Uploading: {os.path.basename(file_path)}")
            upload_chunk(file_path, output_dir, api_key)
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
        result = retrieve_chunk(file_path, output_dir, api_key)
        
        if result == "processing":
            processing_count += 1
        elif result == "failed":
            failed += 1
        elif result is None:
            failed += 1
            # Error message is already printed by retrieve_chunk
        else:
            successful += 1
            print(f"✓ Success\n")

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

