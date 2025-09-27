"""
Author: Claude Code using Sonnet 4
Date: 2025-09-26
PURPOSE: Thread-safe WebSocket connection manager to replace the broken SSE global dictionary architecture
SRP and DRY check: Pass - Single responsibility for WebSocket lifecycle management, eliminates race conditions
"""

import asyncio
import json
import threading
import time
import weakref
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata"""

    def __init__(self, websocket: WebSocket, plan_id: str, client_id: str = None):
        self.websocket = websocket
        self.plan_id = plan_id
        self.client_id = client_id or str(uuid4())
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = time.time()
        self.is_alive = True

    async def send_message(self, message: dict) -> bool:
        """Send message to WebSocket, return False if connection is dead"""
        try:
            await self.websocket.send_json(message)
            return True
        except (WebSocketDisconnect, ConnectionResetError, RuntimeError):
            self.is_alive = False
            return False
        except Exception as e:
            print(f"WebSocket send error for client {self.client_id}: {e}")
            self.is_alive = False
            return False

    async def send_heartbeat(self) -> bool:
        """Send heartbeat ping, return False if connection is dead"""
        try:
            await self.websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            })
            self.last_heartbeat = time.time()
            return True
        except (WebSocketDisconnect, ConnectionResetError, RuntimeError):
            self.is_alive = False
            return False
        except Exception:
            self.is_alive = False
            return False

    async def close(self):
        """Gracefully close the WebSocket connection"""
        try:
            if self.is_alive:
                await self.websocket.close()
        except Exception:
            pass
        finally:
            self.is_alive = False


class WebSocketManager:
    """
    Thread-safe WebSocket connection manager that replaces the broken SSE architecture.

    Fixes the following critical issues:
    1. Global dictionary race conditions
    2. Thread safety violations
    3. Memory leaks from abandoned connections
    4. Resource leaks from improper cleanup
    5. Poor error handling
    """

    def __init__(self):
        # Thread-safe connection storage
        self._connections: Dict[str, List[WebSocketConnection]] = {}
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        # Connection tracking
        self._client_connections: Dict[str, WebSocketConnection] = {}
        self._active_plans: Set[str] = set()

        # Heartbeat management
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_timeout = 60   # seconds

        # Statistics
        self._total_connections = 0
        self._total_messages_sent = 0
        self._connection_errors = 0

        print("WebSocketManager initialized - replacing SSE global dictionary")

    async def add_connection(self, websocket: WebSocket, plan_id: str) -> str:
        """
        Thread-safely add a WebSocket connection for a plan.
        Returns the client_id for this connection.
        """
        connection = WebSocketConnection(websocket, plan_id)

        with self._lock:
            # Initialize plan connection list if needed
            if plan_id not in self._connections:
                self._connections[plan_id] = []

            # Add connection to plan
            self._connections[plan_id].append(connection)

            # Track client connection
            self._client_connections[connection.client_id] = connection

            # Track active plan
            self._active_plans.add(plan_id)

            # Update statistics
            self._total_connections += 1

            print(f"WebSocket connected: plan_id={plan_id}, client_id={connection.client_id}")
            print(f"Total connections for plan {plan_id}: {len(self._connections[plan_id])}")

            return connection.client_id

    async def remove_connection(self, client_id: str) -> None:
        """Thread-safely remove a WebSocket connection"""
        with self._lock:
            if client_id not in self._client_connections:
                return

            connection = self._client_connections[client_id]
            plan_id = connection.plan_id

            # Remove from plan connections
            if plan_id in self._connections:
                self._connections[plan_id] = [
                    conn for conn in self._connections[plan_id]
                    if conn.client_id != client_id
                ]

                # Clean up empty plan lists
                if not self._connections[plan_id]:
                    del self._connections[plan_id]
                    self._active_plans.discard(plan_id)
                    print(f"All connections closed for plan {plan_id}")

            # Remove client tracking
            del self._client_connections[client_id]

            print(f"WebSocket disconnected: plan_id={plan_id}, client_id={client_id}")

    async def broadcast_to_plan(self, plan_id: str, message: dict) -> int:
        """
        Thread-safely broadcast a message to all connections for a plan.
        Returns the number of successful sends.
        """
        successful_sends = 0
        dead_connections = []

        with self._lock:
            if plan_id not in self._connections:
                return 0

            # Get a snapshot of connections to avoid holding lock during async operations
            connections = self._connections[plan_id].copy()

        # Send messages outside the lock to avoid deadlock
        for connection in connections:
            if not connection.is_alive:
                dead_connections.append(connection.client_id)
                continue

            success = await connection.send_message(message)
            if success:
                successful_sends += 1
                self._total_messages_sent += 1
            else:
                dead_connections.append(connection.client_id)
                self._connection_errors += 1

        # Clean up dead connections
        for client_id in dead_connections:
            await self.remove_connection(client_id)

        if successful_sends > 0:
            print(f"Broadcast to plan {plan_id}: {successful_sends} recipients")

        return successful_sends

    async def broadcast_to_all(self, message: dict) -> int:
        """Broadcast a message to all active connections"""
        total_sends = 0

        with self._lock:
            active_plans = list(self._active_plans)

        for plan_id in active_plans:
            sends = await self.broadcast_to_plan(plan_id, message)
            total_sends += sends

        return total_sends

    async def get_plan_connection_count(self, plan_id: str) -> int:
        """Get the number of active connections for a plan"""
        with self._lock:
            if plan_id not in self._connections:
                return 0
            return len(self._connections[plan_id])

    async def cleanup_plan_connections(self, plan_id: str) -> None:
        """Force cleanup all connections for a plan (when plan completes/fails)"""
        with self._lock:
            if plan_id not in self._connections:
                return

            connections = self._connections[plan_id].copy()

        # Close all connections for this plan
        for connection in connections:
            await connection.close()
            await self.remove_connection(connection.client_id)

        print(f"Cleaned up all connections for plan {plan_id}")

    async def start_heartbeat_task(self):
        """Start the heartbeat task to maintain connection health"""
        if self._heartbeat_task is not None:
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        print("WebSocket heartbeat task started")

    async def stop_heartbeat_task(self):
        """Stop the heartbeat task"""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            print("WebSocket heartbeat task stopped")

    async def _heartbeat_loop(self):
        """Background task to send heartbeats and clean up dead connections"""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._send_heartbeats()
                await self._cleanup_dead_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Heartbeat loop error: {e}")

    async def _send_heartbeats(self):
        """Send heartbeat to all connections"""
        with self._lock:
            all_connections = list(self._client_connections.values())

        for connection in all_connections:
            if connection.is_alive:
                await connection.send_heartbeat()

    async def _cleanup_dead_connections(self):
        """Remove connections that haven't responded to heartbeat"""
        current_time = time.time()
        dead_clients = []

        with self._lock:
            for client_id, connection in self._client_connections.items():
                if (current_time - connection.last_heartbeat) > self._heartbeat_timeout:
                    dead_clients.append(client_id)

        for client_id in dead_clients:
            await self.remove_connection(client_id)
            print(f"Removed dead connection: {client_id}")

    def get_statistics(self) -> dict:
        """Get connection statistics"""
        with self._lock:
            return {
                "active_plans": len(self._active_plans),
                "total_connections": len(self._client_connections),
                "total_connections_ever": self._total_connections,
                "total_messages_sent": self._total_messages_sent,
                "connection_errors": self._connection_errors,
                "plans_with_connections": list(self._active_plans)
            }

    async def shutdown(self):
        """Gracefully shutdown the WebSocket manager"""
        print("Shutting down WebSocketManager...")

        # Stop heartbeat task
        await self.stop_heartbeat_task()

        # Close all connections
        with self._lock:
            all_connections = list(self._client_connections.values())

        for connection in all_connections:
            await connection.close()

        # Clear all data structures
        with self._lock:
            self._connections.clear()
            self._client_connections.clear()
            self._active_plans.clear()

        print("WebSocketManager shutdown complete")


# Global WebSocket manager instance (thread-safe replacement for progress_streams)
websocket_manager = WebSocketManager()