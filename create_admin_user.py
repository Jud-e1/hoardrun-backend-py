#!/usr/bin/env python3
"""
Script to create an admin user in the database.
This can be run on Render or locally to create admin users.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the fintech_backend directory to the path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

from app.services.user_service_admin import UserServiceAdmin
from app.database.config import get_db


async def delete_existing_admin(email: str) -> bool:
    """Delete existing admin user if it exists."""
    try:
        print(f"🔧 Checking for existing admin user: {email}")

        # Create admin user service
        user_service_admin = UserServiceAdmin()

        # Get database session
        db_gen = get_db()
        db = next(db_gen)

        try:
            # Check if user exists
            from app.repositories.database_repository import UserRepository
            user_repo = UserRepository(db)
            existing_user = user_repo.get_user_by_email(email)

            if existing_user:
                print(f"   Found existing admin user with ID: {existing_user.id}")
                # Delete the user
                result = await user_service_admin.delete_user_admin(
                    user_id=existing_user.id,
                    reason="Recreating admin user",
                    deleted_by="system",
                    db=db
                )
                if result:
                    print(f"✅ Successfully deleted existing admin user")
                    return True
                else:
                    print(f"❌ Failed to delete existing admin user")
                    return False
            else:
                print(f"   No existing admin user found")
                return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Error deleting existing admin: {type(e).__name__}: {e}")
        return False


async def create_admin_user(email: str, password: str, first_name: str, last_name: str, phone: str = None, country: str = "US"):
    """Create an admin user in the database."""
    try:
        print(f"🔧 Creating admin user: {email}")

        # Create admin user service
        user_service_admin = UserServiceAdmin()

        # Get database session
        db_gen = get_db()
        db = next(db_gen)

        try:
            # Create admin user data
            admin_data = {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone,
                "country": country,
                "role": "admin",
                "is_active": True,
                "email_verified": True  # Admin users are pre-verified
            }

            # Create admin user
            result = await user_service_admin.create_user_admin(
                admin_data,
                created_by="system",  # System created
                db=db
            )

            print(f"✅ Admin user created successfully!")
            print(f"   ID: {result['id']}")
            print(f"   Email: {result['email']}")
            print(f"   Name: {result['first_name']} {result['last_name']}")
            print(f"   Role: {result['role']}")
            print(f"   Status: {'Active' if result['is_active'] else 'Inactive'}")
            print(f"   Email Verified: {result['email_verified']}")
            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Admin user creation failed: {type(e).__name__}: {e}")
        return False


async def main():
    """Main function to create the specific admin user."""
    # First delete existing admin
    success_delete = await delete_existing_admin("hoardrun@gmail.com")
    if not success_delete:
        print("⚠️  Warning: Could not delete existing admin user, but continuing with creation...")

    success = await create_admin_user(
        email="hoardrun@gmail.com",
        password="hoardrun.1",
        first_name="System",
        last_name="Administrator",
        phone="+1234567890",
        country="US"
    )

    if success:
        print("\n🎉 Admin user creation completed successfully!")
        print("You can now login to the admin panel with:")
        print("   Email: hoardrun@gmail.com")
        print("   Password: hoardrun.1")
        print("   Role: admin")
    else:
        print("\n❌ Admin user creation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
