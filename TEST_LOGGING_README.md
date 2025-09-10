# Pytest with Timestamped Logging

This project is configured to automatically generate timestamped log files for each pytest run.

## Usage Options

### Option 1: Custom Python Script (Recommended)
```bash
python run_tests.py [pytest arguments]
```

Examples:
```bash
# Run all tests with timestamped logs
python run_tests.py

# Run specific test file with verbose output
python run_tests.py tests/unit/mapping/test_mapper.py -v

# Run tests with coverage
python run_tests.py --cov=src tests/

# Run only unit tests
python run_tests.py tests/unit
```

### Option 2: Direct Poetry Command (Manual log file naming)
```bash
poetry run pytest --log-file=tests/logs/pytest_run_$(date +%Y-%m-%d_%H-%M-%S).log
```

## Generated Files

Each test run creates timestamped files in the `tests/logs/` directory:

- **`pytest_run_YYYY-MM-DD_HH-MM-SS.log`** - Detailed test logs with DEBUG level + test results summary
- **`pytest_junit_YYYY-MM-DD_HH-MM-SS.xml`** - JUnit XML report for CI/CD integration

### Log File Contents

The `.log` file contains:
1. **Application logs** - DEBUG/INFO/ERROR messages from your code during test execution
2. **Test results summary** - Appended at the end with pass/fail counts and exit code

### XML File Purpose

The `.xml` file is a **JUnit XML report** containing:
- Structured test results for CI/CD systems (Jenkins, GitHub Actions, etc.)
- Individual test case results, timing, and failure details
- Machine-readable format for automated test reporting

## Configuration

The `pytest.ini` file is configured with:
- Live logging during test execution
- Structured log format with timestamps
- Automatic log file generation
- Enhanced console output

## Log Format

Log entries include:
- Timestamp
- Log level
- Logger name
- Message
- File and line number (in log files)

Example log entry:
```
2025-09-10 11:35:33 [    INFO] src.services.mapping.ubl_mapper: UBL Mapping erfolgreich abgeschlossen. (ubl_mapper.py:113)
```
