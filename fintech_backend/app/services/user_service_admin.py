"""
Admin-specific user service methods for comprehensive user administration.
"""

import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.exceptions import ValidationException, UserNotFoundException
from ..config.logging import get_logger
from .user_service import pwd_context

logger = get_logger(__name__)


class UserServiceAdmin:
    """Admin-specific user service methods."""

    async def get_all_users_paginated(self, db: Session, page: int = 1, limit: int = 20,
                                    search: Optional[str] = None, sort_by: str = "created_at",
                                    sort_order: str = "desc") -> Dict[str, Any]:
        """
        Get all users with pagination, search, and sorting (Admin only).

        Args:
            db: Database session
            page: Page number
            limit: Items per page
            search: Search query
            sort_by: Sort field
            sort_order: Sort order

        Returns:
            Dict: Paginated user results
        """
        try:
            logger.info(f"Getting users with pagination: page {page}, limit {limit}")

            from ..database.models import User

            # Build query
            query = db.query(User)

            # Apply search filter
            if search:
                search_filter = f"%{search}%"
                query = query.filter(
                    (User.email.ilike(search_filter)) |
                    (User.first_name.ilike(search_filter)) |
                    (User.last_name.ilike(search_filter)) |
                    (User.phone_number.ilike(search_filter))
                )

            # Get total count
            total = query.count()

            # Apply sorting
            if sort_order == "desc":
                query = query.order_by(getattr(User, sort_by).desc())
            else:
                query = query.order_by(getattr(User, sort_by).asc())

            # Apply pagination
            offset = (page - 1) * limit
            users = query.offset(offset).limit(limit).all()

            # Convert to dict format
            user_list = []
            for user in users:
                user_dict = {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "email_verified": user.email_verified,
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                    "date_of_birth": user.date_of_birth,
                    "country": user.country,
                    "id_number": user.id_number,
                    "bio": user.bio,
                    "profile_picture_url": user.profile_picture_url,
                    "status": user.status,
                    "role": user.role,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                user_list.append(user_dict)

            # Calculate pagination info
            total_pages = (total + limit - 1) // limit

            return {
                "users": user_list,
                "total": total,
                "pages": total_pages,
                "page": page,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting paginated users: {e}")
            raise ValidationException(f"Failed to retrieve users: {str(e)}")

    async def search_users_advanced(self, db: Session, filters: Dict[str, Any],
                                  page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """
        Advanced search and filter users (Admin only).

        Args:
            db: Database session
            filters: Search filters
            page: Page number
            limit: Items per page

        Returns:
            Dict: Filtered user results
        """
        try:
            logger.info("Advanced user search")

            from ..database.models import User

            query = db.query(User)

            # Apply filters
            if filters.get("email"):
                query = query.filter(User.email.ilike(f"%{filters['email']}%"))
            if filters.get("first_name"):
                query = query.filter(User.first_name.ilike(f"%{filters['first_name']}%"))
            if filters.get("last_name"):
                query = query.filter(User.last_name.ilike(f"%{filters['last_name']}%"))
            if filters.get("role"):
                query = query.filter(User.role == filters["role"])
            if filters.get("is_active") is not None:
                query = query.filter(User.is_active == filters["is_active"])
            if filters.get("email_verified") is not None:
                query = query.filter(User.email_verified == filters["email_verified"])
            if filters.get("country"):
                query = query.filter(User.country.ilike(f"%{filters['country']}%"))
            if filters.get("created_after"):
                query = query.filter(User.created_at >= filters["created_after"])
            if filters.get("created_before"):
                query = query.filter(User.created_at <= filters["created_before"])

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (page - 1) * limit
            users = query.offset(offset).limit(limit).all()

            # Convert to dict format
            user_list = []
            for user in users:
                user_dict = {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "email_verified": user.email_verified,
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                    "date_of_birth": user.date_of_birth,
                    "country": user.country,
                    "id_number": user.id_number,
                    "bio": user.bio,
                    "profile_picture_url": user.profile_picture_url,
                    "status": user.status,
                    "role": user.role,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                user_list.append(user_dict)

            total_pages = (total + limit - 1) // limit

            return {
                "users": user_list,
                "total": total,
                "pages": total_pages,
                "page": page,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error in advanced user search: {e}")
            raise ValidationException(f"Search failed: {str(e)}")

    async def get_user_by_id_admin(self, user_id: str, db: Session) -> Dict[str, Any]:
        """
        Get user by ID with full admin details (Admin only).

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Dict: Complete user information
        """
        try:
            logger.info(f"Getting user by ID (admin): {user_id}")

            from ..database.models import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundException(f"User {user_id} not found")

            # Return complete user data including sensitive information
            return {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "email_verified": user.email_verified,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "date_of_birth": user.date_of_birth,
                "country": user.country,
                "id_number": user.id_number,
                "bio": user.bio,
                "profile_picture_url": user.profile_picture_url,
                "status": user.status,
                "role": user.role,
                "password_hash": user.password_hash,  # Include for admin view
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "last_password_change": user.last_password_change.isoformat() if user.last_password_change else None,
                "failed_login_attempts": user.failed_login_attempts or 0,
                "locked_until": user.locked_until.isoformat() if user.locked_until else None
            }

        except UserNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise ValidationException(f"Failed to retrieve user: {str(e)}")

    async def create_user_admin(self, user_data: Dict[str, Any], created_by: str, db: Session) -> Dict[str, Any]:
        """
        Create a new user (Admin only).

        Args:
            user_data: User creation data
            created_by: Admin user ID who created this user
            db: Database session

        Returns:
            Dict: Created user information
        """
        try:
            logger.info(f"Creating user (admin): {user_data.get('email')}")

            from ..database.models import User

            # Hash password
            password_hash = pwd_context.hash(user_data["password"])

            # Create user
            new_user = User(
                email=user_data["email"],
                password_hash=password_hash,
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                phone_number=user_data.get("phone_number"),
                date_of_birth=user_data.get("date_of_birth"),
                country=user_data.get("country"),
                bio=user_data.get("bio"),
                role=user_data.get("role", "user"),
                is_active=user_data.get("is_active", True),
                email_verified=user_data.get("email_verified", False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            logger.info(f"User created: {new_user.id}")
            return {
                "id": new_user.id,
                "email": new_user.email,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "role": new_user.role,
                "is_active": new_user.is_active,
                "email_verified": new_user.email_verified,
                "created_at": new_user.created_at.isoformat()
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise ValidationException(f"User creation failed: {str(e)}")

    async def update_user_admin(self, user_id: str, update_data: Dict[str, Any],
                              updated_by: str, db: Session) -> Dict[str, Any]:
        """
        Update user details (Admin only).

        Args:
            user_id: User ID to update
            update_data: Data to update
            updated_by: Admin user ID performing the update
            db: Database session

        Returns:
            Dict: Updated user information
        """
        try:
            logger.info(f"Updating user (admin): {user_id}")

            from ..database.models import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundException(f"User {user_id} not found")

            # Update fields
            for key, value in update_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            user.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(user)

            logger.info(f"User updated: {user_id}")
            return {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_active": user.is_active,
                "updated_at": user.updated_at.isoformat()
            }

        except UserNotFoundException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user {user_id}: {e}")
            raise ValidationException(f"User update failed: {str(e)}")

    async def update_user_status_admin(self, user_id: str, is_active: bool, reason: Optional[str],
                                     updated_by: str, db: Session) -> Dict[str, Any]:
        """
        Update user active status (Admin only).

        Args:
            user_id: User ID
            is_active: New active status
            reason: Reason for status change
            updated_by: Admin user ID
            db: Database session

        Returns:
            Dict: Updated user information
        """
        try:
            logger.info(f"Updating user status (admin): {user_id} -> {is_active}")

            from ..database.models import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundException(f"User {user_id} not found")

            user.is_active = is_active
            user.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(user)

            # Log the status change (would integrate with audit service)
            logger.info(f"User {user_id} status changed to {is_active} by {updated_by}. Reason: {reason}")

            return {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "updated_at": user.updated_at.isoformat()
            }

        except UserNotFoundException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user status {user_id}: {e}")
            raise ValidationException(f"Status update failed: {str(e)}")

    async def delete_user_admin(self, user_id: str, reason: Optional[str],
                              deleted_by: str, db: Session) -> Dict[str, Any]:
        """
        Delete user account (Admin only).

        Args:
            user_id: User ID to delete
            reason: Reason for deletion
            deleted_by: Admin user ID performing deletion
            db: Database session

        Returns:
            Dict: Deletion result
        """
        try:
            logger.info(f"Deleting user (admin): {user_id}")

            from ..database.models import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundException(f"User {user_id} not found")

            # Store deletion info before deleting
            deletion_info = {
                "id": user.id,
                "email": user.email,
                "deleted_at": datetime.utcnow().isoformat(),
                "deleted_by": deleted_by,
                "reason": reason
            }

            # Delete user (cascade will handle related data)
            db.delete(user)
            db.commit()

            # Log the deletion
            logger.info(f"User {user_id} deleted by {deleted_by}. Reason: {reason}")

            return deletion_info

        except UserNotFoundException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting user {user_id}: {e}")
            raise ValidationException(f"User deletion failed: {str(e)}")

    async def bulk_user_action_admin(self, user_ids: List[str], action: str, reason: Optional[str],
                                   performed_by: str, db: Session) -> Dict[str, Any]:
        """
        Perform bulk actions on multiple users (Admin only).

        Args:
            user_ids: List of user IDs
            action: Action to perform ('activate', 'deactivate', 'delete', 'verify_email')
            reason: Reason for the action
            performed_by: Admin user ID performing the action
            db: Database session

        Returns:
            Dict: Action results
        """
        try:
            logger.info(f"Bulk {action} on {len(user_ids)} users by {performed_by}")

            from ..database.models import User

            successful = []
            failed = []

            for user_id in user_ids:
                try:
                    if action == "activate":
                        await self.update_user_status_admin(user_id, True, reason, performed_by, db)
                        successful.append(user_id)
                    elif action == "deactivate":
                        await self.update_user_status_admin(user_id, False, reason, performed_by, db)
                        successful.append(user_id)
                    elif action == "delete":
                        await self.delete_user_admin(user_id, reason, performed_by, db)
                        successful.append(user_id)
                    elif action == "verify_email":
                        user = db.query(User).filter(User.id == user_id).first()
                        if user:
                            user.email_verified = True
                            user.updated_at = datetime.utcnow()
                            db.commit()
                            successful.append(user_id)
                        else:
                            failed.append({"user_id": user_id, "error": "User not found"})
                    else:
                        failed.append({"user_id": user_id, "error": f"Invalid action: {action}"})

                except Exception as e:
                    failed.append({"user_id": user_id, "error": str(e)})

            result = {
                "action": action,
                "total_requested": len(user_ids),
                "successful": len(successful),
                "failed": len(failed),
                "successful_ids": successful,
                "failed_details": failed,
                "performed_by": performed_by,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Bulk action completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error in bulk action: {e}")
            raise ValidationException(f"Bulk action failed: {str(e)}")

    async def get_user_statistics_admin(self, db: Session) -> Dict[str, Any]:
        """
        Get comprehensive user statistics (Admin only).

        Args:
            db: Database session

        Returns:
            Dict: User statistics
        """
        try:
            logger.info("Getting user statistics (admin)")

            from ..database.models import User

            # Get basic counts
            total_users = db.query(func.count(User.id)).scalar()
            active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
            inactive_users = db.query(func.count(User.id)).filter(User.is_active == False).scalar()
            verified_users = db.query(func.count(User.id)).filter(User.email_verified == True).scalar()
            unverified_users = db.query(func.count(User.id)).filter(User.email_verified == False).scalar()

            # Get role distribution
            role_counts = db.query(User.role, func.count(User.id)).group_by(User.role).all()
            roles = {role: count for role, count in role_counts}

            # Get country distribution (top 10)
            country_counts = db.query(User.country, func.count(User.id)).filter(
                User.country.isnot(None)
            ).group_by(User.country).order_by(func.count(User.id).desc()).limit(10).all()
            countries = {country: count for country, count in country_counts}

            # Get registration trends (last 30 days)
            thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            thirty_days_ago = thirty_days_ago.replace(day=thirty_days_ago.day - 30)

            recent_registrations = db.query(func.count(User.id)).filter(
                User.created_at >= thirty_days_ago
            ).scalar()

            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "verified_users": verified_users,
                "unverified_users": unverified_users,
                "role_distribution": roles,
                "top_countries": countries,
                "recent_registrations": recent_registrations,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise ValidationException(f"Statistics retrieval failed: {str(e)}")
