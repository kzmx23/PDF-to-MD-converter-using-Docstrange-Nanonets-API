import re
import os
import glob
from .pdf_processor import parse_start_page_from_filename

def renumber_markdown_files(base_input_path, output_dir):
    """
    Finds and processes all markdown files in the output directory
    that correspond to the base input file.
    """
    if not os.path.exists(output_dir):
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    base_name = os.path.splitext(os.path.basename(base_input_path))[0]

    # For DJVU files, the converted PDF has "_converted" suffix
    if base_input_path.lower().endswith('.djvu'):
        base_name = f"{base_name}_converted"

    # Use glob to find all matching markdown files
    search_pattern = os.path.join(output_dir, f"{base_name}_pages_*.md")
    md_files = glob.glob(search_pattern)

    if not md_files:
        print(f"No markdown files found for pattern: {search_pattern}")
        return

    # Sort files based on the starting page number to process them in order
    def sort_key(filepath):
        match = re.search(r'_pages_(\d+)_', filepath)
        return int(match.group(1)) if match else 0

    md_files.sort(key=sort_key)
    
    print(f"Found {len(md_files)} markdown files to process for '{base_name}'...")
    for md_file in md_files:
        process_single_md_file(md_file)

def process_single_md_file(md_file_path):
    """
    Processes a single markdown file to renumber the '## Page X' tags.
    """
    print(f"\n--- Processing: {os.path.basename(md_file_path)} ---")
    
    # 1. Parse filename for page range
    filename = os.path.basename(md_file_path)
    match = re.search(r'_pages_(\d+)_(\d+)\.md$', filename)
    if not match:
        print(f"  ✗ Could not parse page range from filename. Skipping.")
        return

    start_page_from_name = int(match.group(1))
    end_page_from_name = int(match.group(2))
    print(f"  Filename expects page range: {start_page_from_name}-{end_page_from_name}")

    # 2. Read file content
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except IOError as e:
        print(f"  ✗ Error reading file: {e}")
        return

    # 3. Find all page markers
    page_markers = list(re.finditer(r"## Page (\d+)", content))
    if not page_markers:
        print(f"  ✓ No '## Page X' markers found. Skipping.")
        return

    first_page_in_content = int(page_markers[0].group(1))
    print(f"  Found {len(page_markers)} page markers. First page found in content is: {first_page_in_content}")

    # 4. Check if renumbering is needed
    if first_page_in_content == start_page_from_name:
        print(f"  ✓ Page numbering is already correct. Skipping.")
        return

    print("  ! Page numbering is incorrect. Renumbering required.")
    
    # 5. Validation Check
    num_pages_in_file = len(page_markers)
    num_pages_in_name = end_page_from_name - start_page_from_name + 1
    if num_pages_in_file != num_pages_in_name:
        print(f"  ⚠ WARNING: Page count mismatch!")
        print(f"    - Pages found in file content: {num_pages_in_file}")
        print(f"    - Pages expected from filename: {num_pages_in_name}")
        # Continue with renumbering as per user request, but the warning is important.
    
    # 6. Perform Renumbering
    page_counter = start_page_from_name
    
    def replacer(match):
        nonlocal page_counter
        new_page_marker = f"## Page {page_counter}"
        page_counter += 1
        return new_page_marker

    new_content = re.sub(r"## Page (\d+)", replacer, content)
    
    last_renumbered_page = page_counter - 1
    
    # Final validation check after renumbering
    print(f"  → Renumbered pages from {start_page_from_name} to {last_renumbered_page}.")
    if last_renumbered_page != end_page_from_name:
        print(f"  ⚠ WARNING: The last renumbered page ({last_renumbered_page}) does not match the expected end page from filename ({end_page_from_name}).")
        
    # 7. Write content back to the file
    try:
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  ✓ Successfully updated and saved file.")
    except IOError as e:
        print(f"  ✗ Error writing updated content to file: {e}")

if __name__ == '__main__':
    # Example of how to run this module directly for testing
    # This part will not be executed when imported by main.py
    
    # Create dummy files for testing
    if not os.path.exists("output"):
        os.makedirs("output")
        
    # File 1: Correctly numbered
    with open("output/test_book_pages_1_2.md", "w", encoding="utf-8") as f:
        f.write("Some text\n\n## Page 1\n\nContent 1\n\n## Page 2\n\nContent 2")
        
    # File 2: Incorrectly numbered
    with open("output/test_book_pages_3_5.md", "w", encoding="utf-8") as f:
        f.write("Some text\n\n## Page 1\n\nContent 1\n\n## Page 2\n\nContent 2\n\n## Page 3\n\nContent 3")

    # File 3: Mismatch count
    with open("output/test_book_pages_6_8.md", "w", encoding="utf-8") as f:
        f.write("Some text\n\n## Page 1\n\nContent 1\n\n## Page 2\n\nContent 2")
        
    print("--- Running direct test of renumberer.py ---")
    renumber_markdown_files("test_book.pdf", "output")
    print("--------------------------------------------")
    
    # Clean up dummy files
    os.remove("output/test_book_pages_1_2.md")
    os.remove("output/test_book_pages_3_5.md")
    os.remove("output/test_book_pages_6_8.md")


def validate_chunks_for_concatenation(base_name, output_dir, expected_start_page=1):
    """
    Validates that all conditions are met for concatenation:
    1. No lock files exist for any chunks
    2. All chunks have corresponding .md files
    3. Page ranges are continuous (cover expected_start_page to last_page with no gaps)

    Args:
        base_name: Base name of the file (without extension)
        output_dir: Directory containing the chunk files
        expected_start_page: Expected starting page number (default: 1).
                            Used for files with _from_XXX_page pattern.

    Returns (valid, message, md_files, total_pages, start_page) tuple.
    """
    # Find all chunk PDFs
    pdf_pattern = os.path.join(output_dir, f"{glob.escape(base_name)}_pages_*.pdf")
    chunk_pdfs = glob.glob(pdf_pattern)

    # Find all MD files
    md_pattern = os.path.join(output_dir, f"{glob.escape(base_name)}_pages_*.md")
    md_files = glob.glob(md_pattern)

    # Find all lock files
    lock_pattern = os.path.join(output_dir, f"{glob.escape(base_name)}_pages_*.pdf.lock")
    lock_files = glob.glob(lock_pattern)

    # Check 1: No lock files should exist
    if lock_files:
        lock_names = [os.path.basename(f) for f in lock_files]
        return False, f"Lock files still exist (processing not complete): {lock_names}", None, 0, expected_start_page

    if not md_files:
        return False, "No markdown files found", None, 0, expected_start_page

    # Parse page ranges from all sources
    def parse_page_range(filepath):
        match = re.search(r'_pages_(\d+)_(\d+)\.(pdf|md)', filepath)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    # Get page ranges from PDFs and MDs
    pdf_ranges = set()
    for pdf in chunk_pdfs:
        start, end = parse_page_range(pdf)
        if start is not None:
            pdf_ranges.add((start, end))

    md_ranges = set()
    for md in md_files:
        start, end = parse_page_range(md)
        if start is not None:
            md_ranges.add((start, end))

    # Check 2: All PDFs should have corresponding MDs
    if pdf_ranges:
        missing_mds = pdf_ranges - md_ranges
        if missing_mds:
            missing_str = [f"pages_{s}_{e}" for s, e in sorted(missing_mds)]
            return False, f"Missing MD files for chunks: {missing_str}", None, 0, expected_start_page

    # Check 3: Page ranges should be continuous
    sorted_ranges = sorted(md_ranges, key=lambda x: x[0])

    if not sorted_ranges:
        return False, "No valid page ranges found", None, 0, expected_start_page

    # Detect actual start page from the first chunk
    first_start, _ = sorted_ranges[0]

    # If expected_start_page is 1 but chunks start at a different page,
    # auto-detect the start page from the chunks
    actual_start_page = first_start

    # Verify ranges are continuous (no gaps) from the actual start
    expected_next = actual_start_page
    for start, end in sorted_ranges:
        if start != expected_next:
            return False, f"Gap in page ranges: expected page {expected_next}, but found chunk starting at {start}", None, 0, actual_start_page
        expected_next = end + 1

    total_pages = sorted_ranges[-1][1]

    # Sort md_files for return
    def sort_key(filepath):
        match = re.search(r'_pages_(\d+)_', filepath)
        return int(match.group(1)) if match else 0
    md_files.sort(key=sort_key)

    return True, f"Validation passed: {len(md_files)} chunks covering pages {actual_start_page}-{total_pages}", md_files, total_pages, actual_start_page


def concatenate_markdown_files(base_input_path, output_dir):
    """
    Finds, renumbers, and then concatenates all markdown files for a given base file.
    Validates that all conditions are met before proceeding.
    """
    print("\n=== Starting Markdown Concatenation Process ===")

    base_name = os.path.splitext(os.path.basename(base_input_path))[0]

    # For DJVU files, the converted PDF has "_converted" suffix
    if base_input_path.lower().endswith('.djvu'):
        base_name = f"{base_name}_converted"

    # Detect start page from filename
    start_page = parse_start_page_from_filename(base_input_path)

    # Step 1: Validate all conditions are met
    print("\nStep 1: Validating chunks...")
    valid, message, md_files, total_pages, actual_start_page = validate_chunks_for_concatenation(base_name, output_dir, start_page)
    print(f"  {message}")

    if not valid:
        print("\n✗ Concatenation aborted - validation failed.")
        print("==============================================")
        return

    # Step 2: Run page renumbering
    print("\nStep 2: Running page renumbering pre-check...")
    renumber_markdown_files(base_input_path, output_dir)
    print("\n--- Renumbering pre-check complete ---\n")

    # Step 3: Find files again (renumbering doesn't change file list)
    search_pattern = os.path.join(output_dir, f"{base_name}_pages_*.md")
    md_files = glob.glob(search_pattern)

    if not md_files:
        print(f"No markdown files found for concatenation with pattern: {search_pattern}")
        return

    # Sort files numerically by starting page
    def sort_key(filepath):
        match = re.search(r'_pages_(\d+)_', filepath)
        return int(match.group(1)) if match else 0
    md_files.sort(key=sort_key)

    print(f"Step 3: Found {len(md_files)} markdown files to concatenate.")

    # Determine final filename - use actual start page from chunks
    first_file = md_files[0]
    last_file = md_files[-1]

    first_match = re.search(r'_pages_(\d+)_(\d+)\.md$', os.path.basename(first_file))
    last_match = re.search(r'_pages_(\d+)_(\d+)\.md$', os.path.basename(last_file))

    if not first_match or not last_match:
        print(f"  ✗ Error: Could not parse page numbers from filenames. Aborting concatenation.")
        return

    start_page_from_first_file = first_match.group(1)
    end_page_from_last_file = last_match.group(2)
    final_filename = f"{base_name}_concat_pages_{start_page_from_first_file}_{end_page_from_last_file}.md"
    final_filepath = os.path.join(output_dir, final_filename)

    print(f"Step 4: Determined final output file name: {final_filename}")

    # Concatenate content
    all_content = []
    print("Step 5: Reading and combining files...")
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                all_content.append(f.read())
            print(f"  - Appended {os.path.basename(md_file)}")
        except IOError as e:
            print(f"  ✗ Error reading file {md_file}: {e}. Aborting.")
            return

    # Join with a clear separator
    final_content = "\n\n---\n\n".join(all_content)

    # Write final concatenated file
    try:
        with open(final_filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"\nStep 6: Successfully created concatenated file: {final_filepath}")
        print("==============================================")

    except IOError as e:
        print(f"\n  ✗ Error writing final concatenated file: {e}")
        print("==============================================")
