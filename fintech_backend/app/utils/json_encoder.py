"""
Custom JSON encoder for handling datetime and other non-serializable objects.
"""
import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from enum import Enum


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime, Decimal, UUID, and Enum objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def custom_json_response(content, status_code: int = 200, headers=None):
    """Create a JSON response with custom encoder."""
    json_content = json.dumps(content, cls=CustomJSONEncoder, ensure_ascii=False)
    return json_content
