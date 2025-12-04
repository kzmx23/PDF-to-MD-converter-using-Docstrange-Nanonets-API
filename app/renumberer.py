import re
import os
import glob

def renumber_markdown_files(base_input_path, output_dir):
    """
    Finds and processes all markdown files in the output directory
    that correspond to the base input file.
    """
    if not os.path.exists(output_dir):
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    base_name = os.path.splitext(os.path.basename(base_input_path))[0]
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


def concatenate_markdown_files(base_input_path, output_dir):
    """
    Finds, renumbers, and then concatenates all markdown files for a given base file.
    """
    print("\n=== Starting Markdown Concatenation Process ===")
    
    # 1. Ensure files are correctly numbered before concatenation
    print("\nStep 1: Running page renumbering pre-check...")
    renumber_markdown_files(base_input_path, output_dir)
    print("\n--- Renumbering pre-check complete ---\n")

    # 2. Find all relevant markdown files again
    base_name = os.path.splitext(os.path.basename(base_input_path))[0]
    search_pattern = os.path.join(output_dir, f"{base_name}_pages_*.md")
    md_files = glob.glob(search_pattern)

    if not md_files:
        print(f"No markdown files found for concatenation with pattern: {search_pattern}")
        return

    # 3. Sort files numerically by starting page
    def sort_key(filepath):
        match = re.search(r'_pages_(\d+)_', filepath)
        return int(match.group(1)) if match else 0
    md_files.sort(key=sort_key)
    
    print(f"Step 2: Found {len(md_files)} markdown files to concatenate.")

    # 4. Determine final filename
    last_file = md_files[-1]
    match = re.search(r'_pages_(\d+)_(\d+)\.md$', os.path.basename(last_file))
    if not match:
        print(f"  ✗ Error: Could not parse final page number from '{os.path.basename(last_file)}'. Aborting concatenation.")
        return
        
    end_page_from_last_file = match.group(2)
    final_filename = f"{base_name}_concat_pages_1_{end_page_from_last_file}.md"
    final_filepath = os.path.join(output_dir, final_filename)
    
    print(f"Step 3: Determined final output file name: {final_filename}")

    # 5. Concatenate content
    all_content = []
    print("Step 4: Reading and combining files...")
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
    
    # 6. Write final concatenated file
    try:
        with open(final_filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"\nStep 5: Successfully created concatenated file: {final_filepath}")
        print("==============================================")

    except IOError as e:
        print(f"\n  ✗ Error writing final concatenated file: {e}")
        print("==============================================")
