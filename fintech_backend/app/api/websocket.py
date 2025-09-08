"""
WebSocket API endpoints for real-time features.
Handles WebSocket connections, authentication, and real-time messaging.
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.responses import HTMLResponse

from app.core.websocket import (
    manager,
    authenticate_websocket,
    handle_websocket_message,
    broadcast_notification,
    broadcast_transaction_update,
    broadcast_balance_update,
    broadcast_market_update,
    broadcast_system_announcement
)
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time notifications.
    
    Features:
    - JWT authentication required
    - Real-time notifications
    - Transaction updates
    - Balance updates
    - System announcements
    - Market data updates (if subscribed)
    
    Query Parameters:
    - token: JWT authentication token
    
    Message Types (Client -> Server):
    - ping: Health check
    - join_room: Join a specific room for group messaging
    - leave_room: Leave a specific room
    - subscribe_notifications: Subscribe to specific notification types
    
    Message Types (Server -> Client):
    - connection_established: Connection successful
    - pong: Response to ping
    - notification: Real-time notification
    - transaction_update: Transaction status update
    - balance_update: Account balance update
    - market_update: Market data update
    - system_announcement: System-wide announcement
    - error: Error message
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token required")
        return
    
    try:
        # Authenticate the WebSocket connection
        user_data = await authenticate_websocket(websocket, token)
        user_id = user_data["user_id"]
        
        # Connect the WebSocket
        await manager.connect(websocket, user_id, user_data)
        
        try:
            while True:
                # Wait for messages from the client
                data = await websocket.receive_text()
                
                try:
                    # Parse the JSON message
                    message = json.loads(data)
                    
                    # Handle the message
                    await handle_websocket_message(websocket, message)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from WebSocket: {data}")
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": "now"
                    }, websocket)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {e}")
        finally:
            # Clean up the connection
            manager.disconnect(websocket)
            
    except AuthenticationError as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")

@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        dict: Connection statistics including total connections, users, and room info
    """
    return {
        "success": True,
        "data": {
            "total_connections": manager.get_connection_count(),
            "unique_users": manager.get_user_count(),
            "rooms": manager.get_room_info(),
            "timestamp": "now"
        }
    }

@router.post("/broadcast/notification")
async def broadcast_notification_endpoint(
    notification_data: dict,
    user_id: Optional[str] = None
):
    """
    Broadcast a notification via WebSocket.
    
    Args:
        notification_data: The notification data to send
        user_id: Optional specific user ID to send to
        
    Returns:
        dict: Success response
    """
    try:
        await broadcast_notification(notification_data, user_id)
        
        return {
            "success": True,
            "message": "Notification broadcasted successfully",
            "target": f"user {user_id}" if user_id else "all users"
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast notification: {str(e)}"
        )

@router.post("/broadcast/transaction")
async def broadcast_transaction_endpoint(
    transaction_data: dict,
    user_id: str
):
    """
    Broadcast a transaction update via WebSocket.
    
    Args:
        transaction_data: The transaction data
        user_id: The user ID to notify
        
    Returns:
        dict: Success response
    """
    try:
        await broadcast_transaction_update(transaction_data, user_id)
        
        return {
            "success": True,
            "message": "Transaction update broadcasted successfully",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast transaction update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast transaction update: {str(e)}"
        )

@router.post("/broadcast/balance")
async def broadcast_balance_endpoint(
    balance_data: dict,
    user_id: str
):
    """
    Broadcast a balance update via WebSocket.
    
    Args:
        balance_data: The balance data
        user_id: The user ID to notify
        
    Returns:
        dict: Success response
    """
    try:
        await broadcast_balance_update(balance_data, user_id)
        
        return {
            "success": True,
            "message": "Balance update broadcasted successfully",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast balance update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast balance update: {str(e)}"
        )

@router.post("/broadcast/market")
async def broadcast_market_endpoint(
    market_data: dict,
    room: str = "market_data"
):
    """
    Broadcast market data updates via WebSocket.
    
    Args:
        market_data: The market data
        room: The room to broadcast to
        
    Returns:
        dict: Success response
    """
    try:
        await broadcast_market_update(market_data, room)
        
        return {
            "success": True,
            "message": "Market update broadcasted successfully",
            "room": room
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast market update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast market update: {str(e)}"
        )

@router.post("/broadcast/announcement")
async def broadcast_announcement_endpoint(
    announcement: dict
):
    """
    Broadcast a system announcement via WebSocket.
    
    Args:
        announcement: The announcement data
        
    Returns:
        dict: Success response
    """
    try:
        await broadcast_system_announcement(announcement)
        
        return {
            "success": True,
            "message": "System announcement broadcasted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast system announcement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast system announcement: {str(e)}"
        )

@router.get("/test")
async def websocket_test_page():
    """
    Simple HTML page for testing WebSocket connections.
    
    Returns:
        HTMLResponse: Test page for WebSocket connections
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .message { margin: 5px 0; padding: 10px; border-radius: 5px; }
            .sent { background-color: #e3f2fd; }
            .received { background-color: #f3e5f5; }
            .error { background-color: #ffebee; color: #c62828; }
            .success { background-color: #e8f5e8; color: #2e7d32; }
            input, button { margin: 5px; padding: 8px; }
            #messages { height: 400px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>WebSocket Test Page</h1>
            
            <div>
                <input type="text" id="token" placeholder="JWT Token" style="width: 300px;">
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
            </div>
            
            <div>
                <input type="text" id="messageInput" placeholder="Message (JSON)" style="width: 400px;">
                <button onclick="sendMessage()">Send</button>
                <button onclick="ping()">Ping</button>
            </div>
            
            <div>
                <input type="text" id="roomInput" placeholder="Room name" style="width: 200px;">
                <button onclick="joinRoom()">Join Room</button>
                <button onclick="leaveRoom()">Leave Room</button>
            </div>
            
            <div id="status" class="message">Disconnected</div>
            <div id="messages"></div>
        </div>

        <script>
            let ws = null;
            const messages = document.getElementById('messages');
            const status = document.getElementById('status');

            function addMessage(message, type = 'received') {
                const div = document.createElement('div');
                div.className = `message ${type}`;
                div.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${message}`;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }

            function updateStatus(message, type = 'success') {
                status.className = `message ${type}`;
                status.textContent = message;
            }

            function connect() {
                const token = document.getElementById('token').value;
                if (!token) {
                    updateStatus('Please enter a JWT token', 'error');
                    return;
                }

                const wsUrl = `ws://localhost:8000/ws/notifications?token=${encodeURIComponent(token)}`;
                ws = new WebSocket(wsUrl);

                ws.onopen = function(event) {
                    updateStatus('Connected to WebSocket', 'success');
                    addMessage('Connected to WebSocket', 'success');
                };

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addMessage(JSON.stringify(data, null, 2), 'received');
                };

                ws.onclose = function(event) {
                    updateStatus(`Disconnected: ${event.code} - ${event.reason}`, 'error');
                    addMessage(`Connection closed: ${event.code} - ${event.reason}`, 'error');
                };

                ws.onerror = function(error) {
                    updateStatus('WebSocket error', 'error');
                    addMessage('WebSocket error occurred', 'error');
                };
            }

            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                    updateStatus('Disconnected', 'error');
                }
            }

            function sendMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateStatus('Not connected', 'error');
                    return;
                }

                const message = document.getElementById('messageInput').value;
                if (!message) return;

                try {
                    const jsonMessage = JSON.parse(message);
                    ws.send(JSON.stringify(jsonMessage));
                    addMessage(JSON.stringify(jsonMessage, null, 2), 'sent');
                    document.getElementById('messageInput').value = '';
                } catch (e) {
                    updateStatus('Invalid JSON message', 'error');
                }
            }

            function ping() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateStatus('Not connected', 'error');
                    return;
                }

                const pingMessage = { type: 'ping' };
                ws.send(JSON.stringify(pingMessage));
                addMessage(JSON.stringify(pingMessage, null, 2), 'sent');
            }

            function joinRoom() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateStatus('Not connected', 'error');
                    return;
                }

                const room = document.getElementById('roomInput').value;
                if (!room) return;

                const message = { type: 'join_room', room: room };
                ws.send(JSON.stringify(message));
                addMessage(JSON.stringify(message, null, 2), 'sent');
            }

            function leaveRoom() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateStatus('Not connected', 'error');
                    return;
                }

                const room = document.getElementById('roomInput').value;
                if (!room) return;

                const message = { type: 'leave_room', room: room };
                ws.send(JSON.stringify(message));
                addMessage(JSON.stringify(message, null, 2), 'sent');
            }

            // Example messages
            document.getElementById('messageInput').placeholder = 'Example: {"type": "subscribe_notifications", "types": ["transaction", "balance"]}';
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
