import os
import re
import math
from pypdf import PdfReader, PdfWriter


def parse_start_page_from_filename(file_path):
    """
    Parses the filename for _from_XXX_page pattern.
    Returns the starting page number (XXX) if found, otherwise returns 1.

    Example:
        'book_from_100_page.pdf' -> 100
        'document.pdf' -> 1
    """
    filename = os.path.basename(file_path)
    match = re.search(r'_from_(\d+)_page', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 1


def analyze_pdf(file_path):
    """
    Analyzes the PDF file to get its size in MB and number of pages.
    """
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    reader = PdfReader(file_path)
    num_pages = len(reader.pages)
    return file_size_mb, num_pages

def calculate_chunks(file_size_mb, num_pages, start_page=1):
    """
    Calculates the splitting plan based on file size and page count.
    Returns a list of tuples (start_page, end_page).
    start_page and end_page are 1-based inclusive.

    Args:
        file_size_mb: File size in megabytes
        num_pages: Total number of pages in the file
        start_page: Page number to start processing from (default: 1).
                    Pages before start_page will be ignored.
    """
    chunks = []

    # Calculate the effective range we're processing
    effective_pages = num_pages - start_page + 1

    if effective_pages <= 0:
        # Invalid range - start_page is beyond the document
        return []

    # Estimate size of the portion we're processing
    effective_size_mb = file_size_mb * (effective_pages / num_pages)

    if effective_size_mb > 50:
        # Split by size logic
        avg_page_size_mb = effective_size_mb / effective_pages
        pages_per_40mb = math.floor(40 / avg_page_size_mb)

        # Ensure chunk doesn't exceed 190 pages (API limit is 200)
        # Also ensure at least 1 page per chunk to avoid infinite loops if pages are huge
        pages_per_chunk = max(1, min(pages_per_40mb, 190))

        current_page = start_page
        while current_page <= num_pages:
            end_page = min(current_page + pages_per_chunk - 1, num_pages)
            chunks.append((current_page, end_page))
            current_page = end_page + 1

    elif effective_pages > 200:
        # Split by page count logic (file size <= 50MB but pages > 200)
        pages_per_chunk = 190
        current_page = start_page
        while current_page <= num_pages:
            end_page = min(current_page + pages_per_chunk - 1, num_pages)
            chunks.append((current_page, end_page))
            current_page = end_page + 1
    else:
        # No splitting needed - single chunk from start_page to end
        chunks.append((start_page, num_pages))

    return chunks

def split_pdf(file_path, chunks, output_dir):
    """
    Splits the PDF file into chunks based on the plan.
    Returns a list of paths to the created files.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    created_files = []
    
    reader = PdfReader(file_path)
    
    for start_page, end_page in chunks:
        # If the chunk covers the whole file, just copy or return original path?
        # The requirement implies we should always save with the naming convention if split?
        # Actually, if no split is needed, we might handle it differently, but here we assume
        # this function is called when splitting is needed OR to standardize naming.
        # Let's strictly follow the naming convention: file_name_pages_N_M
        
        output_filename = f"{base_name}_pages_{start_page}_{end_page}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        writer = PdfWriter()
        # pypdf pages are 0-indexed
        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])
            
        with open(output_path, "wb") as f:
            writer.write(f)
            
        created_files.append(output_path)
        
    return created_files
