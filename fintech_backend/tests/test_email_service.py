"""
Test file for email service functionality.
This test sends a verification email to kipkorirbiiaron@gmail.com
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to the path to import the app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.email_service import get_email_service
from app.config.settings import get_settings
from app.config.logging import get_logger

logger = get_logger(__name__)

async def test_verification_email():
    """Test sending a verification email to kipkorirbiiaron@gmail.com"""

    try:
        # Get settings and check if API key is configured
        settings = get_settings()

        if not settings.resend_api_key:
            logger.error("RESEND_API_KEY environment variable is not set!")
            print("❌ RESEND_API_KEY environment variable is not set!")
            print("Please set your Resend API key in the environment variables.")
            return False

        # Get email service instance
        email_service = get_email_service()

        # Test email address
        test_email = "kipkorirbiiaron@gmail.com"

        # Generate a test verification token
        test_token = "test-verification-token-12345"

        logger.info(f"Sending verification email to {test_email}")

        # Send verification email
        success = await email_service.send_verification_email(test_email, test_token)

        if success:
            logger.info(f"✅ Verification email sent successfully to {test_email}")
            print(f"✅ Verification email sent successfully to {test_email}")
            print("Please check your email inbox (and spam folder) for the verification email.")
            return True
        else:
            logger.error(f"❌ Failed to send verification email to {test_email}")
            print(f"❌ Failed to send verification email to {test_email}")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing email service: {e}")
        print(f"❌ Error testing email service: {e}")
        return False

async def test_password_reset_email():
    """Test sending a password reset email to kipkorirbiiaron@gmail.com"""

    try:
        # Get settings and check if API key is configured
        settings = get_settings()

        if not settings.resend_api_key:
            logger.error("RESEND_API_KEY environment variable is not set!")
            print("❌ RESEND_API_KEY environment variable is not set!")
            print("Please set your Resend API key in the environment variables.")
            return False

        # Get email service instance
        email_service = get_email_service()

        # Test email address
        test_email = "kipkorirbiiaron@gmail.com"

        # Generate a test reset token
        test_token = "test-reset-token-67890"

        logger.info(f"Sending password reset email to {test_email}")

        # Send password reset email
        success = await email_service.send_password_reset_email(test_email, test_token)

        if success:
            logger.info(f"✅ Password reset email sent successfully to {test_email}")
            print(f"✅ Password reset email sent successfully to {test_email}")
            print("Please check your email inbox (and spam folder) for the password reset email.")
            return True
        else:
            logger.error(f"❌ Failed to send password reset email to {test_email}")
            print(f"❌ Failed to send password reset email to {test_email}")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing email service: {e}")
        print(f"❌ Error testing email service: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting Email Service Tests")
    print("=" * 50)

    # Test verification email
    print("\n📧 Testing Verification Email...")
    verification_success = await test_verification_email()

    # Test password reset email
    print("\n🔑 Testing Password Reset Email...")
    reset_success = await test_password_reset_email()

    print("\n" + "=" * 50)
    if verification_success and reset_success:
        print("✅ All email tests completed successfully!")
    else:
        print("❌ Some email tests failed. Check the logs above for details.")

if __name__ == "__main__":
    # Load environment variables from .env file if it exists
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📄 Loaded environment variables from {env_file}")

    # Run the tests
    asyncio.run(main())
