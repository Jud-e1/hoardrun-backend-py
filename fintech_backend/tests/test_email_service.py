"""
Test file for email service functionality.
This test sends a verification email to kipkorirbiiaron@gmail.com
"""

import pytest
import os
import sys
from pathlib import Path

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
