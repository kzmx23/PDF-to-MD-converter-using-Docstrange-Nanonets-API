import os
import math
from pypdf import PdfReader, PdfWriter

def analyze_pdf(file_path):
    """
    Analyzes the PDF file to get its size in MB and number of pages.
    """
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    reader = PdfReader(file_path)
    num_pages = len(reader.pages)
    return file_size_mb, num_pages

def calculate_chunks(file_size_mb, num_pages):
    """
    Calculates the splitting plan based on file size and page count.
    Returns a list of tuples (start_page, end_page).
    start_page and end_page are 1-based inclusive.
    """
    chunks = []
    
    if file_size_mb > 50:
        # Split by size logic
        avg_page_size_mb = file_size_mb / num_pages
        pages_per_40mb = math.floor(40 / avg_page_size_mb)

        # Ensure chunk doesn't exceed 190 pages (API limit is 200)
        # Also ensure at least 1 page per chunk to avoid infinite loops if pages are huge
        pages_per_chunk = max(1, min(pages_per_40mb, 190))

        current_page = 1
        while current_page <= num_pages:
            end_page = min(current_page + pages_per_chunk - 1, num_pages)
            chunks.append((current_page, end_page))
            current_page = end_page + 1
            
    elif num_pages > 200:
        # Split by page count logic (file size <= 50MB but pages > 200)
        pages_per_chunk = 190
        current_page = 1
        while current_page <= num_pages:
            end_page = min(current_page + pages_per_chunk - 1, num_pages)
            chunks.append((current_page, end_page))
            current_page = end_page + 1
    else:
        # No splitting needed
        chunks.append((1, num_pages))
        
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
