import os
import subprocess
import shutil

def is_ddjvu_installed():
    """
    Checks if ddjvu command-line tool is available.
    """
    return shutil.which("ddjvu") is not None

def convert_djvu_to_pdf(djvu_path, output_pdf_path=None):
    """
    Converts a DJVU file to PDF using the ddjvu command-line tool.

    Args:
        djvu_path: Path to the input DJVU file
        output_pdf_path: Path for the output PDF file. If None, creates one in the same directory.

    Returns:
        Path to the generated PDF file on success, None on failure.
    """
    if not os.path.exists(djvu_path):
        print(f"Error: DJVU file not found: {djvu_path}")
        return None

    if not is_ddjvu_installed():
        print("Error: ddjvu tool not found. Please install djvulibre-bin package:")
        print("  Ubuntu/Debian: sudo apt-get install djvulibre-bin")
        print("  macOS: brew install djvulibre")
        print("  Arch Linux: sudo pacman -S djvulibre")
        return None

    # Determine output path
    if output_pdf_path is None:
        base_name = os.path.splitext(djvu_path)[0]
        output_pdf_path = f"{base_name}_converted.pdf"

    # Ensure output directory exists
    output_dir = os.path.dirname(output_pdf_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Converting DJVU to PDF: {os.path.basename(djvu_path)} -> {os.path.basename(output_pdf_path)}")

    try:
        # Run ddjvu command
        # -format=pdf: output format
        # -quality=85: image quality (1-100)
        # -verbose: show progress
        result = subprocess.run(
            ["ddjvu", "-format=pdf", "-quality=85", djvu_path, output_pdf_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            if os.path.exists(output_pdf_path) and os.path.getsize(output_pdf_path) > 0:
                print(f"✓ Successfully converted to PDF: {output_pdf_path}")
                return output_pdf_path
            else:
                print(f"Error: PDF file was not created or is empty")
                return None
        else:
            print(f"Error: ddjvu conversion failed with exit code {result.returncode}")
            if result.stderr:
                print(f"Error details: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("Error: Conversion timed out after 5 minutes")
        return None
    except Exception as e:
        print(f"Error during conversion: {e}")
        return None
