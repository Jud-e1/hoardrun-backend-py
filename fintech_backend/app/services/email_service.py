"""
Email service for sending emails using Resend API.
"""
import logging
from typing import Optional, Dict, Any
from pathlib import Path

import resend
from jinja2 import Template

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailService:
    """Service for sending emails using Resend API."""

    def __init__(self):
        """Initialize the email service with Resend API key."""
        self.api_key = settings.resend_api_key
        if self.api_key:
            resend.api_key = self.api_key
        else:
            logger.warning("Resend API key not configured")

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        text_content: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Send an email using Resend API.

        Args:
            to: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            from_email: Sender email address (optional)
            text_content: Plain text content (optional)
            **kwargs: Additional parameters for Resend API

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.api_key:
            logger.warning("Resend API key not configured, skipping email send")
            return False

        try:
            sender = from_email or settings.email_from

            params = {
                "from": sender,
                "to": [to],
                "subject": subject,
                "html": html_content,
                **kwargs
            }

            if text_content:
                params["text"] = text_content

            response = resend.Emails.send(params)
            logger.info(f"Email sent successfully to {to}: {response}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {str(e)}")
            return False

    async def send_verification_email(
        self,
        to: str,
        verification_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send email verification email.

        Args:
            to: Recipient email address
            verification_token: Email verification token
            user_name: User's name (optional)

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        subject = settings.email_verification_subject

        # Create verification URL (adjust the URL pattern as needed)
        verification_url = f"https://hoardrun.vercel.app/verify-email?token={verification_token}"

        # Simple HTML template for verification email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Welcome to {settings.app_name}!</h2>

                <p>Hello{user_name and f' {user_name}' or ''},</p>

                <p>Thank you for signing up! Please verify your email address by clicking the link below:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}"
                       style="background-color: #007bff; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Verify Email Address
                    </a>
                </div>

                <p>If the button doesn't work, you can also copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{verification_url}</p>

                <p>This link will expire in 24 hours.</p>

                <p>If you didn't create an account, please ignore this email.</p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">

                <p style="color: #666; font-size: 12px;">
                    This is an automated message from {settings.app_name}. Please do not reply to this email.
                </p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

    async def send_password_reset_email(
        self,
        to: str,
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send password reset email.

        Args:
            to: Recipient email address
            reset_token: Password reset token
            user_name: User's name (optional)

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        subject = settings.email_password_reset_subject

        # Create reset URL (adjust the URL pattern as needed)
        reset_url = f"https://hoardrun.vercel.app/reset-password?token={reset_token}"

        # Simple HTML template for password reset email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Password Reset Request</h2>

                <p>Hello{user_name and f' {user_name}' or ''},</p>

                <p>We received a request to reset your password. Click the link below to create a new password:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}"
                       style="background-color: #dc3545; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Reset Password
                    </a>
                </div>

                <p>If the button doesn't work, you can also copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{reset_url}</p>

                <p>This link will expire in 1 hour.</p>

                <p>If you didn't request a password reset, please ignore this email. Your password will remain unchanged.</p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">

                <p style="color: #666; font-size: 12px;">
                    This is an automated message from {settings.app_name}. Please do not reply to this email.
                </p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)


# Global email service instance
email_service = EmailService()


def get_email_service() -> EmailService:
    """Get email service instance."""
    return email_service
