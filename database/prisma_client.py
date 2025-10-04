#!/usr/bin/env python3
"""
Prisma Client Wrapper

Provides easy access to Prisma Client Python with connection management.
"""

from prisma import Prisma
from typing import Optional
import asyncio

# Global Prisma client instance
_prisma_client: Optional[Prisma] = None
_connection_lock = asyncio.Lock()


async def get_prisma() -> Prisma:
    """Get or create the global Prisma client instance."""
    global _prisma_client

    async with _connection_lock:
        if _prisma_client is None:
            _prisma_client = Prisma(auto_register=True)
            await _prisma_client.connect()

        return _prisma_client


async def disconnect_prisma():
    """Disconnect the Prisma client."""
    global _prisma_client

    if _prisma_client is not None:
        await _prisma_client.disconnect()
        _prisma_client = None


# For FastAPI dependency injection
async def get_db() -> Prisma:
    """FastAPI dependency to get Prisma client.

    Usage:
        @app.get("/users")
        async def get_users(db: Prisma = Depends(get_db)):
            users = await db.user.find_many()
            return users
    """
    return await get_prisma()
