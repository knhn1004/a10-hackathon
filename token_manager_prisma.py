#!/usr/bin/env python3
"""
API Token Management with Prisma

Handles creation, validation, and revocation of API tokens using Prisma ORM.
"""

import secrets
import time
import hashlib
import uuid as uuid_module
from typing import Optional, List
from datetime import datetime

from database.prisma_client import get_prisma


async def generate_token(user_id: str, username: str, name: str, description: str = "") -> str:
    """Generate a new API token for a user.
    
    Args:
        user_id: GitHub user ID  
        username: GitHub username
        name: Friendly name for the token
        description: Optional description
        
    Returns:
        The generated token (only shown once!)
    """
    db = await get_prisma()
    
    # Ensure user exists
    user = await db.users.find_unique(where={'githubId': user_id})
    if not user:
        # Create user if doesn't exist
        user = await db.users.create(
            data={
                'id': str(uuid_module.uuid4()),
                'githubId': user_id,
                'username': username,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow(),
            }
        )
    
    # Generate secure random token
    token = f"mcp_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Create token record
    await db.api_tokens.create(
        data={
            'id': str(uuid_module.uuid4()),
            'userId': user.id,
            'tokenHash': token_hash,
            'name': name,
            'description': description,
            'active': True,
            'usageCount': 0,
        }
    )
    
    return token


async def validate_token(token: str) -> Optional[dict]:
    """Validate an API token.
    
    Args:
        token: The token to validate
        
    Returns:
        Token data if valid, None otherwise
    """
    if not token or not token.startswith("mcp_"):
        return None
    
    db = await get_prisma()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Find token with user relationship
    token_record = await db.api_tokens.find_unique(
        where={'tokenHash': token_hash},
        include={'users': True}
    )
    
    if not token_record or not token_record.active:
        return None
    
    # Update usage stats
    await db.api_tokens.update(
        where={'id': token_record.id},
        data={
            'lastUsedAt': datetime.utcnow(),
            'usageCount': {'increment': 1}
        }
    )
    
    return {
        'user_id': token_record.users.username if token_record.users else 'unknown',
        'name': token_record.name,
        'usage_count': token_record.usageCount + 1,
    }


async def list_tokens(user_id: str) -> List[dict]:
    """List all tokens for a user.
    
    Args:
        user_id: GitHub user ID
        
    Returns:
        List of token metadata
    """
    db = await get_prisma()
    
    # Find user
    user = await db.users.find_unique(
        where={'githubId': user_id},
        include={'api_tokens': True}
    )
    
    if not user:
        return []
    
    # Convert to dict format
    tokens = []
    for token in user.api_tokens:
        tokens.append({
            'token_hash': token.id,  # Use ID as hash for identification
            'name': token.name,
            'description': token.description,
            'created_at': token.createdAt.timestamp(),
            'last_used': token.lastUsedAt.timestamp() if token.lastUsedAt else None,
            'usage_count': token.usageCount,
            'active': token.active,
        })
    
    # Sort by creation date (newest first)
    tokens.sort(key=lambda x: x['created_at'], reverse=True)
    
    return tokens


async def revoke_token(user_id: str, token_id: str) -> bool:
    """Revoke a token.
    
    Args:
        user_id: GitHub user ID (must match token owner)
        token_id: ID of token to revoke
        
    Returns:
        True if revoked successfully
    """
    db = await get_prisma()
    
    # Find token and verify ownership
    token = await db.api_tokens.find_unique(
        where={'id': token_id},
        include={'users': True}
    )
    
    if not token or not token.users or token.users.githubId != user_id:
        return False
    
    # Mark as inactive
    await db.api_tokens.update(
        where={'id': token_id},
        data={
            'active': False,
            'revokedAt': datetime.utcnow()
        }
    )
    
    return True


async def delete_token(user_id: str, token_id: str) -> bool:
    """Permanently delete a token.
    
    Args:
        user_id: GitHub user ID (must match token owner)
        token_id: ID of token to delete
        
    Returns:
        True if deleted successfully
    """
    db = await get_prisma()
    
    # Find token and verify ownership
    token = await db.api_tokens.find_unique(
        where={'id': token_id},
        include={'users': True}
    )
    
    if not token or not token.users or token.users.githubId != user_id:
        return False
    
    # Delete permanently
    await db.api_tokens.delete(where={'id': token_id})
    
    return True
