#!/usr/bin/env python3
"""
Test runner script for database integration tests.

This script runs the database-related tests to verify PostgreSQL integration.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add the parent directory to the path so we can import our app
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_command(command, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    """Main function to run tests."""
    parser = argparse.ArgumentParser(description="Run database integration tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", "-c", action="store_true", help="Run with coverage")
    parser.add_argument("--specific", "-s", help="Run specific test file or pattern")
    parser.add_argument("--database-only", "-d", action="store_true", 
                       help="Run only database-related tests")
    
    args = parser.parse_args()
    
    print("Database Integration Test Runner")
    print("=" * 60)
    
    # Check if pytest is available
    try:
        import pytest
        print(f"✓ pytest version: {pytest.__version__}")
    except ImportError:
        print("✗ pytest not found. Please install it: pip install pytest")
        return False
    
    # Check if coverage is available if requested
    if args.coverage:
        try:
            import coverage
            print(f"✓ coverage version: {coverage.__version__}")
        except ImportError:
            print("✗ coverage not found. Please install it: pip install pytest-cov")
            return False
    
    # Build pytest command
    pytest_cmd = [sys.executable, "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    if args.coverage:
        pytest_cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Determine which tests to run
    if args.specific:
        test_pattern = args.specific
    elif args.database_only:
        test_pattern = "tests/integration/test_database*.py"
    else:
        test_pattern = "tests/"
    
    pytest_cmd.append(test_pattern)
    
    # Run the tests
    success = run_command(pytest_cmd, "Running pytest")
    
    if success:
        print("\n" + "="*60)
        print("✓ All tests passed!")
        
        if args.coverage:
            print("\nCoverage report generated in htmlcov/index.html")
    else:
        print("\n" + "="*60)
        print("✗ Some tests failed!")
        return False
    
    return True


def run_specific_database_tests():
    """Run specific database integration tests."""
    tests = [
        ("Database Connection Tests", "tests/integration/test_database.py::TestDatabaseConnection"),
        ("User Model Tests", "tests/integration/test_database.py::TestUserModel"),
        ("Account Model Tests", "tests/integration/test_database.py::TestAccountModel"),
        ("Transaction Model Tests", "tests/integration/test_database.py::TestTransactionModel"),
        ("Card Model Tests", "tests/integration/test_database.py::TestCardModel"),
        ("Model Relationships Tests", "tests/integration/test_database.py::TestModelRelationships"),
        ("Health Endpoints Tests", "tests/integration/test_health_endpoints.py"),
        ("Database Init Script Tests", "tests/integration/test_database_init.py"),
    ]
    
    results = []
    
    for description, test_path in tests:
        cmd = [sys.executable, "-m", "pytest", "-v", test_path]
        success = run_command(cmd, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for description, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {description}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} test suites")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    return failed == 0


def check_database_setup():
    """Check if database is properly set up for testing."""
    print("\nChecking database setup...")
    
    try:
        from ..database.config import check_database_connection, get_database_info
        
        # Check connection
        if check_database_connection():
            print("✓ Database connection successful")
            
            # Get database info
            db_info = get_database_info()
            print(f"✓ Database URL: {db_info.get('database_url', 'Unknown')}")
            print(f"✓ Database Version: {db_info.get('database_version', 'Unknown')}")
            
            return True
        else:
            print("✗ Database connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Error checking database: {e}")
        return False


if __name__ == "__main__":
    # Check database setup first
    if not check_database_setup():
        print("\nDatabase setup check failed. Please ensure your database is running and configured correctly.")
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--specific-tests":
        success = run_specific_database_tests()
    else:
        success = main()
    
    sys.exit(0 if success else 1)
