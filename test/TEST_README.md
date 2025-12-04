# Test Documentation for PDF to Markdown Converter

This document describes the test suite for the PDF to Markdown converter application.

## Overview

The test suite verifies all functionality described in `app_desc.md`:

1. PDF analysis (size and page count)
2. File limitation checks (50MB and 200 pages)
3. Chunking logic for splitting files
4. PDF splitting with correct naming conventions
5. Dry-run mode
6. Integration tests with real test files

## Test Structure

The tests are organized into the following classes:

- `TestPDFAnalysis`: Tests for analyzing PDF files
- `TestChunkingLogic`: Tests for calculating split chunks
- `TestPDFSplitting`: Tests for actual PDF splitting operations
- `TestDryRunMode`: Tests for dry-run functionality
- `TestNamingConventions`: Tests for output file naming
- `TestFileLimitations`: Tests for 50MB and 200-page limits
- `TestIntegration`: End-to-end integration tests
- `TestRealFiles`: Tests using actual test PDF files

## Running the Tests

### Prerequisites

1. Ensure you have the virtual environment activated:
   ```bash
   source venv/bin/activate  # On Linux/Mac
   # or
   venv\Scripts\activate  # On Windows
   ```

2. Install test dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run All Tests

```bash
pytest test_app.py -v
```

### Run with Detailed Output

To see print statements and detailed output:

```bash
pytest test_app.py -v -s
```

### Run Specific Test Classes

```bash
# Test PDF analysis only
pytest test_app.py::TestPDFAnalysis -v -s

# Test chunking logic only
pytest test_app.py::TestChunkingLogic -v -s

# Test real files only
pytest test_app.py::TestRealFiles -v -s

# Test dry-run mode
pytest test_app.py::TestDryRunMode -v -s
```

### Run Specific Test Methods

```bash
# Test large file processing
pytest test_app.py::TestRealFiles::test_large_file_processing -v -s

# Test many-pages file processing
pytest test_app.py::TestRealFiles::test_many_pages_file_processing -v -s
```

## Test Files

The test suite uses two real PDF files located in the `test/` directory:

1. **том 1 книга 3.pdf** - A large file (>50MB) used to test size-based splitting
2. **Маклаков А.Г. Общая психология. Учебник для вузов. СПб 2018.pdf** - A file with >200 pages used to test page-based splitting

These files are required for the `TestRealFiles` test class. If they are missing, those tests will be skipped.

## Test Coverage

### 1. PDF Analysis Tests
- Verifies correct calculation of file size in MB
- Verifies correct page count extraction
- Tests with actual test files

### 2. Chunking Logic Tests
- **No splitting**: Files ≤50MB and ≤200 pages remain as single file
- **Size-based splitting**: Files >50MB split into ~40MB chunks
- **Page-based splitting**: Files >200 pages (but ≤50MB) split into 190-page chunks
- Verifies page continuity across chunks
- Verifies all pages are covered

### 3. PDF Splitting Tests
- Verifies correct naming convention: `filename_pages_N_M.pdf`
- Verifies page numbering preservation
- Verifies actual PDF page count in split files

### 4. Dry-Run Mode Tests
- Verifies dry-run displays chunking plan
- Verifies no actual file operations occur
- Tests both splitting and non-splitting scenarios

### 5. Integration Tests
- Tests complete workflow from analysis to output
- Tests with mocked API calls (to avoid actual API usage)
- Tests end-to-end with dry-run mode

### 6. Real File Tests
- Tests actual processing of provided test files
- Displays detailed chunking plans
- Verifies correct behavior for >50MB files
- Verifies correct behavior for >200 page files

## Expected Output

When running tests with `-s` flag, you'll see detailed output including:

```
=== Testing large file: test/том 1 книга 3.pdf ===
Size: 98.XX MB
Pages: XXX

Chunking plan:
  Chunk 1: Pages 1-40 (40 pages)
  Chunk 2: Pages 41-80 (40 pages)
  ...
```

## Continuous Testing

For development, you can run tests in watch mode:

```bash
pytest test_app.py -v -s --tb=short
```

## Troubleshooting

### Test Files Not Found
If you get "Test file not found" warnings, ensure the test PDF files are in the `test/` directory.

### Import Errors
Ensure you're running tests from the project root directory and the virtual environment is activated.

### API Tests Failing
The integration tests use mocked API calls to avoid actual API usage during testing. If you want to test actual API conversion, you'll need to create separate integration tests with valid API credentials.

## Adding New Tests

To add new tests:

1. Create a new test class or add to existing ones
2. Follow the naming convention: `test_*` for test methods
3. Use descriptive names that explain what is being tested
4. Include print statements for debugging (visible with `-s` flag)
5. Use assertions with clear error messages

Example:
```python
def test_my_new_feature(self):
    """Test description"""
    result = my_function()
    assert result == expected, f"Expected {expected}, got {result}"
```

## Test Results Interpretation

- **PASSED**: Test succeeded
- **FAILED**: Test failed with assertion error
- **SKIPPED**: Test was skipped (usually due to missing test files)
- **ERROR**: Test encountered an error before assertions

All tests should PASS when the application is working correctly according to the specifications in `app_desc.md`.
