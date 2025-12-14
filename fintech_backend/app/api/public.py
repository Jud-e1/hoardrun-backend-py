"""
Public API endpoints that don't require authentication.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import os
from sqlalchemy.orm import Session

from ..database.config import get_db
from ..services.user_service_admin import UserServiceAdmin
from ..config.logging import get_logger

router = APIRouter(tags=["Public"])
logger = get_logger(__name__)


@router.get("/user-stats")
async def get_public_user_statistics(db: Session = Depends(get_db)):
    """
    Get public user statistics for the landing page.

    Returns basic user statistics without requiring authentication.
    """
    try:
        logger.info("Getting public user statistics")

        user_service = UserServiceAdmin()
        stats = await user_service.get_user_statistics_admin(db)

        # Return only public-safe statistics
        public_stats = {
            "total_users": stats["total_users"],
            "active_users": stats["active_users"],
            "inactive_users": stats["inactive_users"],
            "verified_users": stats["verified_users"],
            "unverified_users": stats["unverified_users"],
            "role_distribution": stats["role_distribution"],
            "top_countries": stats["top_countries"],
            "recent_registrations": stats["recent_registrations"],
            "generated_at": stats["generated_at"]
        }

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "statistics": public_stats
            }
        )

    except Exception as e:
        logger.error(f"Error getting public user statistics: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Failed to retrieve statistics",
                "message": "Unable to load user statistics at this time"
            }
        )


@router.get("/test")
async def test_endpoint():
    """
    Test endpoint to verify router is working.
    """
    return {"test": "ok", "message": "Public router is working"}
