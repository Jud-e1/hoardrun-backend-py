"""
Response utility functions for API endpoints.
"""

from typing import Any, Dict, Optional


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> Dict[str, Any]:
    """
    Create a standardized success response format.
    
    Args:
        data: The response data
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Standardized response dictionary
    """
    response = {
        "success": True,
        "message": message,
        "status_code": status_code
    }
    
    if data is not None:
        response["data"] = data
        
    return response


def error_response(
    message: str = "An error occurred",
    error_code: Optional[str] = None,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response format.
    
    Args:
        message: Error message
        error_code: Optional error code
        status_code: HTTP status code
        details: Optional additional error details
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "message": message,
        "status_code": status_code
    }
    
    if error_code:
        response["error_code"] = error_code
        
    if details:
        response["details"] = details
        
    return response
