#!/usr/bin/env python3
"""
Test script for phone number and country validation in User model.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import re
from app.database.models import User

def test_phone_validation():
    """Test phone number validation logic."""
    print("Testing Phone Number Validation")
    print("=" * 40)

    # Test cases: (input, expected_result, should_pass)
    test_cases = [
        # Valid cases
        ("+1234567890", "+1234567890", True),  # International with +
        ("1234567890", "1234567890", True),    # Local 10 digits
        ("0123456789", "0123456789", True),    # Local with leading 0
        ("+447911123456", "+447911123456", True),  # UK number
        ("+254712345678", "+254712345678", True),  # Kenya number
        ("9876543210", "9876543210", True),    # 10 digits
        ("123456789012345", "123456789012345", True),  # 15 digits max

        # Invalid cases - too short
        ("123456", None, False),  # Too short (6 digits)
        ("+12345", None, False),  # Too short with +

        # Invalid cases - too long
        ("1234567890123456", None, False),  # Too long (16 digits)
        ("+1234567890123456", None, False),  # Too long with +

        # Edge cases
        ("", "", True),  # Empty string (should be allowed)
        (None, None, True),  # None (should be allowed)

        # Cases with formatting that should be cleaned
        ("+1 (234) 567-8901", "+12345678901", True),  # With formatting
        ("+1.234.567.8901", "+12345678901", True),    # With dots
        ("+1 234 567 8901", "+12345678901", True),    # With spaces
        ("(234) 567-8901", "2345678901", True),       # Local with formatting
        ("234-567-8901", "2345678901", True),         # Local with dashes
    ]

    passed = 0
    failed = 0

    for input_val, expected, should_pass in test_cases:
        try:
            # Create a mock user instance to test validation
            user = User.__new__(User)  # Create without calling __init__

            # Test the validation method directly
            result = user.validate_phone_number('phone_number', input_val)

            if should_pass:
                if result == expected:
                    print(f"✓ PASS: '{input_val}' -> '{result}'")
                    passed += 1
                else:
                    print(f"✗ FAIL: '{input_val}' -> '{result}' (expected '{expected}')")
                    failed += 1
            else:
                print(f"✗ UNEXPECTED PASS: '{input_val}' -> '{result}' (should have failed)")
                failed += 1

        except ValueError as e:
            if not should_pass:
                print(f"✓ PASS: '{input_val}' correctly rejected - {e}")
                passed += 1
            else:
                print(f"✗ FAIL: '{input_val}' unexpectedly rejected - {e}")
                failed += 1
        except Exception as e:
            print(f"✗ ERROR: '{input_val}' caused unexpected error - {e}")
            failed += 1

    print(f"\nPhone validation results: {passed} passed, {failed} failed")
    return failed == 0

def test_country_validation():
    """Test country code validation logic."""
    print("\nTesting Country Code Validation")
    print("=" * 40)

    # Test cases: (input, expected_result, should_pass)
    test_cases = [
        # Valid cases
        ("US", "US", True),   # USA
        ("us", "US", True),   # lowercase
        ("GB", "GB", True),   # UK
        ("KE", "KE", True),   # Kenya
        ("CA", "CA", True),   # Canada
        ("DE", "DE", True),   # Germany

        # Invalid cases - wrong length
        ("USA", None, False),    # Too long
        ("U", None, False),      # Too short
        ("", "", True),          # Empty (should be allowed)
        (None, None, True),      # None (should be allowed)
        ("123", None, False),    # Numbers
        ("U1", None, False),     # Mixed
        ("us ", None, False),    # With space
    ]

    passed = 0
    failed = 0

    for input_val, expected, should_pass in test_cases:
        try:
            # Create a mock user instance to test validation
            user = User.__new__(User)  # Create without calling __init__

            # Test the validation method directly
            result = user.validate_country('country', input_val)

            if should_pass:
                if result == expected:
                    print(f"✓ PASS: '{input_val}' -> '{result}'")
                    passed += 1
                else:
                    print(f"✗ FAIL: '{input_val}' -> '{result}' (expected '{expected}')")
                    failed += 1
            else:
                print(f"✗ UNEXPECTED PASS: '{input_val}' -> '{result}' (should have failed)")
                failed += 1

        except ValueError as e:
            if not should_pass:
                print(f"✓ PASS: '{input_val}' correctly rejected - {e}")
                passed += 1
            else:
                print(f"✗ FAIL: '{input_val}' unexpectedly rejected - {e}")
                failed += 1
        except Exception as e:
            print(f"✗ ERROR: '{input_val}' caused unexpected error - {e}")
            failed += 1

    print(f"\nCountry validation results: {passed} passed, {failed} failed")
    return failed == 0

def test_regex_patterns():
    """Test the regex patterns used in validation."""
    print("\nTesting Regex Patterns")
    print("=" * 40)

    # Phone number regex from the model
    phone_regex = r'^\+?\d{7,15}$'

    # Test phone regex
    print("Phone regex:", phone_regex)
    phone_tests = [
        "+1234567890", "1234567890", "+447911123456", "9876543210",
        "123456", "+12345", "1234567890123456", "+1234567890123456"
    ]

    for test in phone_tests:
        match = bool(re.match(phone_regex, test))
        print(f"  '{test}' -> {'✓' if match else '✗'}")

if __name__ == "__main__":
    print("Validation Testing Script")
    print("=" * 50)

    phone_ok = test_phone_validation()
    country_ok = test_country_validation()
    test_regex_patterns()

    print("\n" + "=" * 50)
    if phone_ok and country_ok:
        print("✓ All validations passed!")
        sys.exit(0)
    else:
        print("✗ Some validations failed!")
        sys.exit(1)
