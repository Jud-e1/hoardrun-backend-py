#!/usr/bin/env python3
"""
Script to create a user in the database.
This can be run on Render or locally to create test users.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the fintech_backend directory to the path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

from ..services.auth_service import AuthService
from ..models.auth import UserRegisterRequest
from ..database.config import get_db


async def create_user(email: str, password: str, first_name: str, last_name: str, phone: str = None, country: str = "US"):
    """Create a user in the database."""
    try:
        print(f"🔧 Creating user: {email}")
        
        # Create auth service
        auth_service = AuthService()
        
        # Create registration request
        register_request = UserRegisterRequest(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            country=country,
            terms_accepted=True
        )
        
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Register user
            result = await auth_service.register_user(register_request, db)
            print(f"✅ User created successfully!")
            print(f"   ID: {result.id}")
            print(f"   Email: {result.email}")
            print(f"   Name: {result.first_name} {result.last_name}")
            print(f"   Status: {result.status}")
            print(f"   Email Verified: {result.email_verified}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ User creation failed: {type(e).__name__}: {e}")
        return False


async def main():
    """Main function to create the specific user."""
    success = await create_user(
        email="judeazane01@gmail.com",
        password="Kendrick@1",
        first_name="Jude",
        last_name="Azane",
        phone="+1234567890",
        country="US"
    )
    
    if success:
        print("\n🎉 User creation completed successfully!")
        print("You can now login with:")
        print("   Email: judeazane01@gmail.com")
        print("   Password: Kendrick@1")
    else:
        print("\n❌ User creation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
