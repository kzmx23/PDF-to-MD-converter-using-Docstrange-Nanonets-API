import os
import sys
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pypdf import PdfReader, PdfWriter
from app.pdf_processor import analyze_pdf, calculate_chunks, split_pdf
from app.converter import convert_file
from io import StringIO
from app.main import main


class TestPDFAnalysis:
    """Test PDF analysis functionality"""

    def test_analyze_pdf_with_real_files(self):
        """Test PDF analysis with the actual test files"""
        # Test file 1: том 1 книга 3.pdf (should be > 50MB)
        test_file_1 = "test/том 1 книга 3.pdf"
        if os.path.exists(test_file_1):
            size_mb, num_pages = analyze_pdf(test_file_1)
            print(f"\nFile: {test_file_1}")
            print(f"Size: {size_mb:.2f} MB")
            print(f"Pages: {num_pages}")
            assert size_mb > 50, f"Expected file size > 50MB, got {size_mb:.2f}MB"
            assert num_pages > 0, "Expected positive page count"

        # Test file 2: Маклаков А.Г. Общая психология. Учебник для вузов. СПб 2018.pdf (should be > 200 pages)
        test_file_2 = "test/Маклаков А.Г. Общая психология. Учебник для вузов. СПб 2018.pdf"
        if os.path.exists(test_file_2):
            size_mb, num_pages = analyze_pdf(test_file_2)
            print(f"\nFile: {test_file_2}")
            print(f"Size: {size_mb:.2f} MB")
            print(f"Pages: {num_pages}")
            assert num_pages > 200, f"Expected > 200 pages, got {num_pages} pages"
            assert size_mb < 50, f"Expected file size < 50MB, got {size_mb:.2f}MB"


class TestChunkingLogic:
    """Test PDF chunking logic for splitting files"""

    def test_no_splitting_for_small_files(self):
        """Files within limits (<=50MB, <=200 pages) should not be split"""
        # 30MB, 100 pages - no splitting needed
        chunks = calculate_chunks(30, 100)
        assert len(chunks) == 1
        assert chunks[0] == (1, 100)

        # 49MB, 200 pages - at the edge, no splitting
        chunks = calculate_chunks(49, 200)
        assert len(chunks) == 1
        assert chunks[0] == (1, 200)

    def test_splitting_by_file_size(self):
        """Files > 50MB should be split into ~40MB chunks"""
        # 100MB file with 100 pages
        # avg page size = 1MB per page
        # pages per 40MB = 40 pages
        size_mb = 100
        num_pages = 100
        chunks = calculate_chunks(size_mb, num_pages)

        print(f"\nSplitting {size_mb}MB file with {num_pages} pages:")
        for i, (start, end) in enumerate(chunks):
            print(f"  Chunk {i+1}: Pages {start}-{end}")

        # Should have multiple chunks
        assert len(chunks) > 1, "Large file should be split into multiple chunks"

        # Verify page continuity
        prev_end = 0
        for start, end in chunks:
            assert start == prev_end + 1, f"Page gap detected: expected {prev_end + 1}, got {start}"
            assert end >= start, "End page should be >= start page"
            prev_end = end

        # Verify all pages are covered
        assert chunks[-1][1] == num_pages, "Last chunk should end at last page"

    def test_splitting_by_page_count(self):
        """Files with >200 pages but <=50MB should be split into 190-page chunks"""
        # 40MB file with 400 pages
        size_mb = 40
        num_pages = 400
        chunks = calculate_chunks(size_mb, num_pages)

        print(f"\nSplitting {size_mb}MB file with {num_pages} pages:")
        for i, (start, end) in enumerate(chunks):
            print(f"  Chunk {i+1}: Pages {start}-{end} ({end-start+1} pages)")

        # Should have multiple chunks
        assert len(chunks) > 1, "File with >200 pages should be split"

        # First chunk should have 190 pages
        assert chunks[0][1] - chunks[0][0] + 1 == 190, "First chunk should have 190 pages"

        # Verify page continuity
        prev_end = 0
        for start, end in chunks:
            assert start == prev_end + 1, f"Page gap: expected {prev_end + 1}, got {start}"
            prev_end = end

        # Verify all pages are covered
        assert chunks[-1][1] == num_pages

    def test_chunking_with_real_test_files(self):
        """Test chunking logic with actual test files"""
        # Test file 1: том 1 книга 3.pdf (>50MB)
        test_file_1 = "test/том 1 книга 3.pdf"
        if os.path.exists(test_file_1):
            size_mb, num_pages = analyze_pdf(test_file_1)
            chunks = calculate_chunks(size_mb, num_pages)

            print(f"\n=== Chunking plan for: {test_file_1} ===")
            print(f"File size: {size_mb:.2f} MB")
            print(f"Total pages: {num_pages}")
            print(f"Number of chunks: {len(chunks)}")
            for i, (start, end) in enumerate(chunks):
                print(f"  Chunk {i+1}: Pages {start}-{end} ({end-start+1} pages)")

            assert len(chunks) > 1, "Large file should be split"
            assert chunks[-1][1] == num_pages, "Should cover all pages"

        # Test file 2: Маклаков (>200 pages)
        test_file_2 = "test/Маклаков А.Г. Общая психология. Учебник для вузов. СПб 2018.pdf"
        if os.path.exists(test_file_2):
            size_mb, num_pages = analyze_pdf(test_file_2)
            chunks = calculate_chunks(size_mb, num_pages)

            print(f"\n=== Chunking plan for: {test_file_2} ===")
            print(f"File size: {size_mb:.2f} MB")
            print(f"Total pages: {num_pages}")
            print(f"Number of chunks: {len(chunks)}")
            for i, (start, end) in enumerate(chunks):
                print(f"  Chunk {i+1}: Pages {start}-{end} ({end-start+1} pages)")

            if num_pages > 200:
                assert len(chunks) > 1, "File with >200 pages should be split"
                assert chunks[-1][1] == num_pages, "Should cover all pages"


class TestPDFSplitting:
    """Test actual PDF file splitting with correct naming"""

    def create_test_pdf(self, num_pages=10):
        """Create a temporary PDF with specified number of pages"""
        writer = PdfWriter()
        for i in range(num_pages):
            writer.add_blank_page(width=612, height=792)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        with open(temp_file.name, 'wb') as f:
            writer.write(f)

        return temp_file.name

    def test_split_pdf_naming_convention(self):
        """Test that split PDFs follow the naming convention: filename_pages_N_M.pdf"""
        test_pdf = self.create_test_pdf(num_pages=50)
        temp_dir = tempfile.mkdtemp()

        try:
            # Create chunks
            chunks = [(1, 20), (21, 40), (41, 50)]

            # Split the PDF
            created_files = split_pdf(test_pdf, chunks, temp_dir)

            # Verify number of files created
            assert len(created_files) == 3, f"Expected 3 files, got {len(created_files)}"

            # Verify naming convention
            base_name = os.path.splitext(os.path.basename(test_pdf))[0]
            expected_names = [
                f"{base_name}_pages_1_20.pdf",
                f"{base_name}_pages_21_40.pdf",
                f"{base_name}_pages_41_50.pdf"
            ]

            for i, created_file in enumerate(created_files):
                filename = os.path.basename(created_file)
                print(f"Created file: {filename}")
                assert filename == expected_names[i], f"Expected {expected_names[i]}, got {filename}"

                # Verify file exists
                assert os.path.exists(created_file), f"File {created_file} should exist"

                # Verify page count
                reader = PdfReader(created_file)
                expected_pages = chunks[i][1] - chunks[i][0] + 1
                assert len(reader.pages) == expected_pages, \
                    f"Expected {expected_pages} pages, got {len(reader.pages)}"

        finally:
            os.unlink(test_pdf)
            shutil.rmtree(temp_dir)

    def test_split_preserves_page_numbering(self):
        """Test that page numbering is preserved correctly across chunks"""
        test_pdf = self.create_test_pdf(num_pages=30)
        temp_dir = tempfile.mkdtemp()

        try:
            chunks = [(1, 10), (11, 20), (21, 30)]
            created_files = split_pdf(test_pdf, chunks, temp_dir)

            # Verify page continuity
            for i, (start, end) in enumerate(chunks):
                reader = PdfReader(created_files[i])
                actual_pages = len(reader.pages)
                expected_pages = end - start + 1

                print(f"Chunk {i+1}: Expected pages {start}-{end} ({expected_pages} pages), "
                      f"got {actual_pages} pages")

                assert actual_pages == expected_pages, \
                    f"Chunk {i+1} should have {expected_pages} pages, got {actual_pages}"

        finally:
            os.unlink(test_pdf)
            shutil.rmtree(temp_dir)


class TestDryRunMode:
    """Test dry-run functionality"""

    @patch('sys.stdout', new_callable=StringIO)
    def test_dry_run_no_splitting(self, mock_stdout):
        """Test dry-run output for files that don't need splitting"""
        from app.main import main

        # Create a small test PDF
        writer = PdfWriter()
        for i in range(10):
            writer.add_blank_page(width=612, height=792)

        test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        with open(test_file.name, 'wb') as f:
            writer.write(f)

        try:
            with patch('sys.argv', ['main.py', test_file.name, '--dry-run']):
                main()

            output = mock_stdout.getvalue()
            print(f"\n=== Dry-run output ===\n{output}")

            assert '--- Dry Run Plan ---' in output, "Should show dry-run plan"
            assert 'No splitting required' in output or 'within limits' in output, \
                "Should indicate no splitting needed"

        finally:
            os.unlink(test_file.name)

    @patch('sys.stdout', new_callable=StringIO)
    def test_dry_run_with_splitting(self, mock_stdout):
        """Test dry-run output showing chunking plan"""
        # We can't easily create a >50MB PDF, but we can test with real files
        test_file = "test/том 1 книга 3.pdf"

        if os.path.exists(test_file):
            from app.main import main

            with patch('sys.argv', ['main.py', test_file, '--dry-run']):
                main()

            output = mock_stdout.getvalue()
            print(f"\n=== Dry-run output for large file ===\n{output}")

            assert '--- Dry Run Plan ---' in output, "Should show dry-run plan"
            assert 'Chunk' in output or 'pages_' in output, "Should show chunk information"


class TestNamingConventions:
    """Test output file naming conventions"""

    def test_output_filename_pattern(self):
        """Test that output filenames follow the pattern: original_name_pages_1_N.md"""
        # Test with a mock file
        base_name = "test_document"
        num_pages = 50

        # Expected pattern: test_document_pages_1_50.md
        expected_pattern = f"{base_name}_pages_1_{num_pages}"

        # The naming should be applied even for non-split files
        chunks = calculate_chunks(30, num_pages)  # Within limits
        assert chunks == [(1, num_pages)]

        # Verify the pattern
        output_name = f"{base_name}_pages_{chunks[0][0]}_{chunks[0][1]}"
        assert output_name == expected_pattern, \
            f"Expected {expected_pattern}, got {output_name}"


class TestFileLimitations:
    """Test PDF file limitation checks"""

    def test_50mb_size_limit_detection(self):
        """Test detection of files >50MB"""
        # Simulate 60MB file
        chunks = calculate_chunks(60, 100)
        assert len(chunks) > 1, "Files >50MB should be split"

        # Simulate 45MB file
        chunks = calculate_chunks(45, 100)
        assert len(chunks) == 1, "Files <=50MB should not be split by size"

    def test_200_page_limit_detection(self):
        """Test detection of files >200 pages"""
        # Simulate 250 pages, 40MB
        chunks = calculate_chunks(40, 250)
        assert len(chunks) > 1, "Files >200 pages should be split"

        # Simulate 190 pages, 40MB
        chunks = calculate_chunks(40, 190)
        assert len(chunks) == 1, "Files <=200 pages should not be split by page count"


class TestIntegration:
    """Integration tests for the complete workflow"""

    def create_test_pdf(self, num_pages=10):
        """Create a temporary PDF with specified number of pages"""
        writer = PdfWriter()
        for i in range(num_pages):
            writer.add_blank_page(width=612, height=792)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        with open(temp_file.name, 'wb') as f:
            writer.write(f)

        return temp_file.name

    def test_end_to_end_with_dry_run(self):
        """Test end-to-end workflow with dry-run mode"""
        test_pdf = self.create_test_pdf(num_pages=50)

        try:
            from app.main import main

            # Test with dry-run
            with patch('sys.argv', ['main.py', test_pdf, '--dry-run']):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()

                    print(f"\n=== End-to-end dry-run test ===\n{output}")

                    # Should complete without errors
                    assert 'Error' not in output or 'Error analyzing PDF' not in output

        finally:
            os.unlink(test_pdf)


class TestRealFiles:
    """Tests using the actual test files provided"""

    def test_large_file_processing(self):
        """Test processing of том 1 книга 3.pdf (>50MB file)"""
        test_file = "test/том 1 книга 3.pdf"

        if not os.path.exists(test_file):
            pytest.skip(f"Test file not found: {test_file}")

        print(f"\n=== Testing large file: {test_file} ===")

        # Analyze
        size_mb, num_pages = analyze_pdf(test_file)
        print(f"Size: {size_mb:.2f} MB")
        print(f"Pages: {num_pages}")

        # Calculate chunks
        chunks = calculate_chunks(size_mb, num_pages)
        print(f"Number of chunks: {len(chunks)}")

        # Display chunking plan
        print("\nChunking plan:")
        for i, (start, end) in enumerate(chunks):
            print(f"  Chunk {i+1}: Pages {start}-{end} ({end-start+1} pages)")

        # Verify splitting is triggered
        assert size_mb > 50, "Test file should be >50MB"
        assert len(chunks) > 1, "Large file should be split into multiple chunks"

        # Verify page continuity
        for i in range(len(chunks) - 1):
            assert chunks[i][1] + 1 == chunks[i+1][0], \
                f"Gap in page numbering between chunk {i+1} and {i+2}"

        # Verify all pages covered
        assert chunks[0][0] == 1, "Should start from page 1"
        assert chunks[-1][1] == num_pages, "Should end at last page"

    def test_many_pages_file_processing(self):
        """Test processing of Маклаков file (>200 pages)"""
        test_file = "test/Маклаков А.Г. Общая психология. Учебник для вузов. СПб 2018.pdf"

        if not os.path.exists(test_file):
            pytest.skip(f"Test file not found: {test_file}")

        print(f"\n=== Testing many-pages file: {test_file} ===")

        # Analyze
        size_mb, num_pages = analyze_pdf(test_file)
        print(f"Size: {size_mb:.2f} MB")
        print(f"Pages: {num_pages}")

        # Calculate chunks
        chunks = calculate_chunks(size_mb, num_pages)
        print(f"Number of chunks: {len(chunks)}")

        # Display chunking plan
        print("\nChunking plan:")
        for i, (start, end) in enumerate(chunks):
            print(f"  Chunk {i+1}: Pages {start}-{end} ({end-start+1} pages)")

        # Verify splitting if >200 pages
        if num_pages > 200:
            assert len(chunks) > 1, "File with >200 pages should be split"

            # Verify page continuity
            for i in range(len(chunks) - 1):
                assert chunks[i][1] + 1 == chunks[i+1][0], \
                    f"Gap in page numbering between chunk {i+1} and {i+2}"

            # Verify all pages covered
            assert chunks[0][0] == 1, "Should start from page 1"
            assert chunks[-1][1] == num_pages, "Should end at last page"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


class TestResumeAndRetrieve:
    """Tests for the resumable and retrieve-only functionality."""

    def create_test_pdf(self, num_pages=1):
        """Create a temporary PDF with a specified number of pages."""
        writer = PdfWriter()
        for i in range(num_pages):
            writer.add_blank_page(width=612, height=792)
        
        # Use a descriptive name for the temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir=self.temp_dir, prefix="test_book_")
        with open(temp_file.name, 'wb') as f:
            writer.write(f)
        return temp_file.name

    def setup_method(self):
        """Set up a temp directory and a test PDF for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_pdf_path = self.create_test_pdf()
        self.output_dir = os.path.join(self.temp_dir, "output")
        # The app creates the output dir, so we don't have to
        
    def teardown_method(self):
        """Clean up the temp directory after each test."""
        shutil.rmtree(self.temp_dir)

    @patch('app.converter.poll_and_retrieve')
    @patch('app.converter.upload_file')
    def test_resume_and_retrieve_workflow(self, mock_upload, mock_poll):
        """Test the full workflow: initial failure, then successful retrieval."""
        from app.main import main

        # --- Stage 1: Initial run, fails during polling ---
        print("\n--- STAGE 1: Initial run (fails) ---")
        
        # Mock setup
        mock_upload.return_value = 123456789  # Use an integer to replicate the bug
        mock_poll.return_value = None  # Simulate polling failure

        with patch('sys.argv', ['app/main.py', self.test_pdf_path, '--output-dir', self.output_dir]):
            main()

        # Assertions for Stage 1
        mock_upload.assert_called_once()
        mock_poll.assert_called_once_with(123456789, os.getenv("API_KEY"), total_pages=1)

        # Find the created chunk and associated lock file
        base_name = os.path.splitext(os.path.basename(self.test_pdf_path))[0]
        chunk_name = f"{base_name}_pages_1_1.pdf"
        chunk_path = os.path.join(self.output_dir, chunk_name)
        lock_file_path = chunk_path + ".lock"

        assert os.path.exists(lock_file_path), "Lock file should have been created on failed poll"
        with open(lock_file_path, "r") as f:
            content = f.read()
            assert content == '123456789', "Lock file should contain the correct record_id as a string"
        print("✓ Stage 1 assertions passed.")

        # --- Stage 2: Second run with --retrieve-only, succeeds ---
        print("\n--- STAGE 2: Retrieve-only run (succeeds) ---")
        
        # Reset mocks
        mock_upload.reset_mock()
        mock_poll.reset_mock()

        # Mock setup for successful retrieval
        mock_upload.side_effect = Exception("Upload should not be called in retrieve-only mode")
        mock_poll.return_value = "# Success"

        with patch('sys.argv', ['app/main.py', self.test_pdf_path, '--output-dir', self.output_dir, '--retrieve-only']):
            main()
            
        # Assertions for Stage 2
        mock_upload.assert_not_called()
        # The ID read from the file will be a string
        mock_poll.assert_called_once_with('123456789', os.getenv("API_KEY"), total_pages=1)

        # Check for final output file
        md_file_path = os.path.join(self.output_dir, f"{base_name}_pages_1_1.md")
        assert os.path.exists(md_file_path), "Markdown file should be created on successful retrieval"
        with open(md_file_path, "r") as f:
            content = f.read()
            assert content == "# Success", "Markdown content should match"
            
        # Check that lock file was deleted
        assert not os.path.exists(lock_file_path), "Lock file should be deleted on success"
        print("✓ Stage 2 assertions passed.")
