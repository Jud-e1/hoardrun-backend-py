"""
Test file for email service functionality.
This test sends a verification email to kipkorirbiiaron@gmail.com
"""

import pytest
import os
import sys
from pathlib import Path
import asyncio

# Add the parent directory to the path to import the app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.email_service import get_email_service
from app.config.settings import get_settings
from app.config.logging import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_verification_email():
    """Test sending a verification email to kipkorirbiiaron@gmail.com"""

    # Get settings and check if API key is configured
    settings = get_settings()

    if not settings.resend_api_key:
        pytest.skip("RESEND_API_KEY environment variable is not set!")

    # Get email service instance
    email_service = get_email_service()

    # Test email address
    test_email = "kipkorirbiiaron@gmail.com"

    # Generate a test verification token
    test_token = "test-verification-token-12345"

    logger.info(f"Sending verification email to {test_email}")

    # Send verification email
    success = await email_service.send_verification_email(test_email, test_token)

    assert success, f"Failed to send verification email to {test_email}"


@pytest.mark.asyncio
async def test_password_reset_email():
    """Test sending a password reset email to kipkorirbiiaron@gmail.com"""

    # Get settings and check if API key is configured
    settings = get_settings()

    if not settings.resend_api_key:
        pytest.skip("RESEND_API_KEY environment variable is not set!")

    # Get email service instance
    email_service = get_email_service()

    # Test email address
    test_email = "kipkorirbiiaron@gmail.com"

    # Generate a test reset token
    test_token = "test-reset-token-67890"

    logger.info(f"Sending password reset email to {test_email}")

    # Send password reset email
    success = await email_service.send_password_reset_email(test_email, test_token)

    assert success, f"Failed to send password reset email to {test_email}"


# Allow direct execution with python
if __name__ == "__main__":
    print("Running email service tests...\n")
    
    async def run_tests():
        """Run all tests manually"""
        settings = get_settings()
        
        if not settings.resend_api_key:
            print("❌ RESEND_API_KEY environment variable is not set!")
            print("Please add RESEND_API_KEY to your .env file")
            return
        
        print(f"✓ Resend API key found: {settings.resend_api_key[:10]}...")
        print(f"✓ Email from: {settings.email_from}\n")
        
        # Test verification email
        print("Test 1: Sending verification email...")
        try:
            await test_verification_email()
            print("✅ Verification email test passed!\n")
        except Exception as e:
            print(f"❌ Verification email test failed: {str(e)}\n")
        
        # Test password reset email
        print("Test 2: Sending password reset email...")
        try:
            await test_password_reset_email()
            print("✅ Password reset email test passed!\n")
        except Exception as e:
            print(f"❌ Password reset email test failed: {str(e)}\n")
    
    # Run the async tests
    asyncio.run(run_tests())