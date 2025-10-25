"""
WebSocket connection manager for real-time features.
Handles WebSocket connections, authentication, and message broadcasting.
"""

import json
import logging
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status
from datetime import datetime
import asyncio
from jose import jwt
from jose.exceptions import JWTError as InvalidTokenError

from ..config.settings import get_settings
from ..core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)
settings = get_settings()

class ConnectionManager:
    """
    Manages WebSocket connections for real-time features.
    
    Features:
    - User-based connection management
    - JWT authentication for WebSocket connections
    - Message broadcasting to specific users or groups
    - Connection health monitoring
    - Automatic cleanup of disconnected clients
    """
    
    def __init__(self):
        # Active connections: user_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Connection metadata: WebSocket -> user info
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        # Room-based connections for group messaging
        self.rooms: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str, user_data: Dict[str, Any]):
        """
        Accept a new WebSocket connection and associate it with a user.
        
        Args:
            websocket: The WebSocket connection
            user_id: The authenticated user ID
            user_data: Additional user information
        """
        await websocket.accept()
        
        # Initialize user connections if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        # Add connection to user's active connections
        self.active_connections[user_id].add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "user_data": user_data
        }
        
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.connection_metadata)}")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "message": "Connected to real-time notifications",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection and clean up associated data.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        if websocket in self.connection_metadata:
            user_id = self.connection_metadata[websocket]["user_id"]
            
            # Remove from user's active connections
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                
                # Clean up empty user connection sets
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # Remove from all rooms
            for room_connections in self.rooms.values():
                room_connections.discard(websocket)
            
            # Remove connection metadata
            del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected for user {user_id}. Total connections: {len(self.connection_metadata)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection.
        
        Args:
            message: The message to send
            websocket: The target WebSocket connection
        """
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def send_to_user(self, message: Dict[str, Any], user_id: str):
        """
        Send a message to all connections of a specific user.
        
        Args:
            message: The message to send
            user_id: The target user ID
        """
        if user_id in self.active_connections:
            # Create a copy of the set to avoid modification during iteration
            connections = self.active_connections[user_id].copy()
            
            for websocket in connections:
                await self.send_personal_message(message, websocket)
    
    async def send_to_room(self, message: Dict[str, Any], room: str):
        """
        Send a message to all connections in a specific room.
        
        Args:
            message: The message to send
            room: The room name
        """
        if room in self.rooms:
            # Create a copy of the set to avoid modification during iteration
            connections = self.rooms[room].copy()
            
            for websocket in connections:
                await self.send_personal_message(message, websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all active connections.
        
        Args:
            message: The message to broadcast
        """
        # Create a copy of the connections to avoid modification during iteration
        all_connections = list(self.connection_metadata.keys())
        
        for websocket in all_connections:
            await self.send_personal_message(message, websocket)
    
    def join_room(self, websocket: WebSocket, room: str):
        """
        Add a WebSocket connection to a room for group messaging.
        
        Args:
            websocket: The WebSocket connection
            room: The room name to join
        """
        if room not in self.rooms:
            self.rooms[room] = set()
        
        self.rooms[room].add(websocket)
        logger.info(f"WebSocket joined room '{room}'. Room size: {len(self.rooms[room])}")
    
    def leave_room(self, websocket: WebSocket, room: str):
        """
        Remove a WebSocket connection from a room.
        
        Args:
            websocket: The WebSocket connection
            room: The room name to leave
        """
        if room in self.rooms:
            self.rooms[room].discard(websocket)
            
            # Clean up empty rooms
            if not self.rooms[room]:
                del self.rooms[room]
            
            logger.info(f"WebSocket left room '{room}'")
    
    def get_user_connections(self, user_id: str) -> Set[WebSocket]:
        """
        Get all active connections for a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Set of WebSocket connections for the user
        """
        return self.active_connections.get(user_id, set())
    
    def get_connection_count(self) -> int:
        """
        Get the total number of active connections.
        
        Returns:
            Total number of active WebSocket connections
        """
        return len(self.connection_metadata)
    
    def get_user_count(self) -> int:
        """
        Get the number of unique users with active connections.
        
        Returns:
            Number of unique users connected
        """
        return len(self.active_connections)
    
    def get_room_info(self) -> Dict[str, int]:
        """
        Get information about all active rooms.
        
        Returns:
            Dictionary mapping room names to connection counts
        """
        return {room: len(connections) for room, connections in self.rooms.items()}

# Global connection manager instance
manager = ConnectionManager()

async def authenticate_websocket(websocket: WebSocket, token: str) -> Dict[str, Any]:
    """
    Authenticate a WebSocket connection using JWT token.
    
    Args:
        websocket: The WebSocket connection
        token: JWT token for authentication
        
    Returns:
        User data from the token
        
    Raises:
        AuthenticationError: If authentication fails
    """
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Extract user information
        user_data = {
            "user_id": user_id,
            "email": payload.get("email"),
            "username": payload.get("username"),
            "role": payload.get("role", "user"),
            "exp": payload.get("exp")
        }
        
        return user_data
        
    except InvalidTokenError as e:
        logger.error(f"WebSocket authentication failed: {e}")
        raise AuthenticationError("Invalid or expired token")
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        raise AuthenticationError("Authentication failed")

async def handle_websocket_message(websocket: WebSocket, message: Dict[str, Any]):
    """
    Handle incoming WebSocket messages from clients.
    
    Args:
        websocket: The WebSocket connection
        message: The received message
    """
    try:
        message_type = message.get("type")
        
        if message_type == "ping":
            # Respond to ping with pong
            await manager.send_personal_message({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)
            
        elif message_type == "join_room":
            # Join a specific room
            room = message.get("room")
            if room:
                manager.join_room(websocket, room)
                await manager.send_personal_message({
                    "type": "room_joined",
                    "room": room,
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)
        
        elif message_type == "leave_room":
            # Leave a specific room
            room = message.get("room")
            if room:
                manager.leave_room(websocket, room)
                await manager.send_personal_message({
                    "type": "room_left",
                    "room": room,
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)
        
        elif message_type == "subscribe_notifications":
            # Subscribe to notification types
            notification_types = message.get("types", [])
            # Store subscription preferences in connection metadata
            if websocket in manager.connection_metadata:
                manager.connection_metadata[websocket]["subscriptions"] = notification_types
                
            await manager.send_personal_message({
                "type": "subscription_updated",
                "subscriptions": notification_types,
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)
        
        else:
            logger.warning(f"Unknown WebSocket message type: {message_type}")
            
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": "Failed to process message",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

# Notification broadcasting functions
async def broadcast_notification(notification_data: Dict[str, Any], user_id: Optional[str] = None):
    """
    Broadcast a notification via WebSocket.
    
    Args:
        notification_data: The notification data to send
        user_id: Optional specific user ID to send to (if None, broadcasts to all)
    """
    message = {
        "type": "notification",
        "data": notification_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if user_id:
        await manager.send_to_user(message, user_id)
    else:
        await manager.broadcast(message)

async def broadcast_transaction_update(transaction_data: Dict[str, Any], user_id: str):
    """
    Broadcast a transaction status update.
    
    Args:
        transaction_data: The transaction data
        user_id: The user ID to notify
    """
    message = {
        "type": "transaction_update",
        "data": transaction_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.send_to_user(message, user_id)

async def broadcast_balance_update(balance_data: Dict[str, Any], user_id: str):
    """
    Broadcast a balance update.
    
    Args:
        balance_data: The balance data
        user_id: The user ID to notify
    """
    message = {
        "type": "balance_update",
        "data": balance_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.send_to_user(message, user_id)

async def broadcast_market_update(market_data: Dict[str, Any], room: str = "market_data"):
    """
    Broadcast market data updates to subscribers.
    
    Args:
        market_data: The market data
        room: The room to broadcast to (default: "market_data")
    """
    message = {
        "type": "market_update",
        "data": market_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.send_to_room(message, room)

async def broadcast_system_announcement(announcement: Dict[str, Any]):
    """
    Broadcast a system-wide announcement.
    
    Args:
        announcement: The announcement data
    """
    message = {
        "type": "system_announcement",
        "data": announcement,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.broadcast(message)
