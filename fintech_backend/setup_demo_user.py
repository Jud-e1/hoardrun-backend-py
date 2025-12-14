#!/usr/bin/env python3
"""
Setup script to create demo user for testing.
This script can be run during deployment or manually to ensure test users exist.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ..services.auth_service import AuthService
from ..models.auth import UserRegisterRequest
from ..database.config import get_db, check_database_connection
from ..database.models import User


async def check_and_create_demo_user():
    """Check if demo user exists and create if not."""
    demo_email = "judeazane01@gmail.com"
    demo_password = "Kendrick@1"

    try:
        print("🔍 Checking database connection...")
        print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
        print(f"🗄️ Database URL: {os.getenv('DATABASE_URL', 'not set')[:50]}...")

        if not check_database_connection():
            print("❌ Database connection failed")
            return False
        print("✅ Database connection successful")
        
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == demo_email).first()
            
            if existing_user:
                print(f"✅ Demo user already exists: {demo_email}")
                print(f"   Status: {existing_user.status}")
                print(f"   Email Verified: {existing_user.email_verified}")
                return True
            
            print(f"🔧 Creating demo user: {demo_email}")
            
            # Create auth service
            auth_service = AuthService()
            
            # Create registration request
            register_request = UserRegisterRequest(
                email=demo_email,
                password=demo_password,
                first_name="Jude",
                last_name="Azane",
                phone_number="+1234567890",
                country="US",
                terms_accepted=True
            )
            
            # Register user
            result = await auth_service.register_user(register_request, db)
            print(f"✅ Demo user created successfully!")
            print(f"   ID: {result.id}")
            print(f"   Email: {result.email}")
            print(f"   Name: {result.first_name} {result.last_name}")
            print(f"   Status: {result.status}")
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error setting up demo user: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main function."""
    print("🚀 Setting up demo user for HoardRun...")
    print("🔧 Version: 1.1 - Enhanced user creation")

    success = await check_and_create_demo_user()

    if success:
        print("\n🎉 Demo user setup completed!")
        print("You can now login with:")
        print("   Email: judeazane01@gmail.com")
        print("   Password: Kendrick@1")
    else:
        print("\n❌ Demo user setup failed!")
        # Don't exit with error to prevent deployment failure
        print("⚠️ Continuing deployment anyway...")
        # sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
