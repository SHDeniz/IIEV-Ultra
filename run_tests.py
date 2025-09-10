#!/usr/bin/env python3
"""
Pytest runner with timestamped logging
Usage: python run_tests.py [pytest arguments]
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def main():
    # Create tests/logs directory if it doesn't exist
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Define log files with timestamp
    log_file = logs_dir / f"pytest_run_{timestamp}.log"
    junit_file = logs_dir / f"pytest_junit_{timestamp}.xml"
    html_file = logs_dir / f"pytest_report_{timestamp}.html"
    
    # Build pytest command
    pytest_args = [
        "poetry", "run", "pytest",
        f"--log-file={log_file}",
        f"--junitxml={junit_file}",
    ]
    
    # Add any additional arguments passed to this script
    pytest_args.extend(sys.argv[1:])
    
    print(f"🧪 Running pytest with timestamped logging...")
    print(f"📄 Log file: {log_file}")
    print(f"📊 JUnit XML: {junit_file}")
    print(f"🚀 Command: {' '.join(pytest_args)}")
    print("-" * 60)
    
    try:
        # Run pytest and capture output
        result = subprocess.run(pytest_args, check=False, capture_output=True, text=True)
        
        # Print the output to console (so you still see it)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # Append test summary to log file
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"PYTEST SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Exit code: {result.returncode}\n")
            # Extract the summary line from stdout
            lines = result.stdout.split('\n')
            for line in lines:
                if 'failed' in line or 'passed' in line or 'error' in line:
                    if '==' in line and ('failed' in line or 'passed' in line):
                        f.write(f"Test Results: {line.strip()}\n")
                        break
            f.write(f"{'='*80}\n\n")
        
        print("-" * 60)
        print(f"✅ Test run completed with exit code: {result.returncode}")
        print(f"📄 Log saved to: {log_file}")
        print(f"📊 JUnit XML saved to: {junit_file}")
        
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n❌ Test run interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
