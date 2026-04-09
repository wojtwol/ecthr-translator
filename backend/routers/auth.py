"""Authentication router and middleware."""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Simple in-memory token store (for production, use Redis or DB)
active_tokens: dict[str, datetime] = {}

security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    """Login request model."""
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    token: Optional[str] = None
    message: str


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash password for comparison."""
    return hashlib.sha256(password.encode()).hexdigest()


def is_auth_enabled() -> bool:
    """Check if authentication is enabled."""
    return bool(settings.app_password and settings.app_password.strip())


def verify_token(token: str) -> bool:
    """Verify if token is valid and not expired."""
    if token not in active_tokens:
        return False

    expiry = active_tokens[token]
    if datetime.now() > expiry:
        # Token expired, remove it
        del active_tokens[token]
        return False

    return True


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> bool:
    """
    Dependency to require authentication on endpoints.

    If auth is not enabled (no password set), always returns True.
    If auth is enabled, validates the Bearer token.
    """
    # If no password is set, skip authentication
    if not is_auth_enabled():
        return True

    # Check for valid token
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if not verify_token(token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with password.

    Returns a token that must be used in Authorization header for all API calls.
    """
    # If no password is configured, allow access
    if not is_auth_enabled():
        return LoginResponse(
            success=True,
            token=None,
            message="Authentication not required"
        )

    # Verify password
    if request.password != settings.app_password:
        logger.warning("Failed login attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid password"
        )

    # Generate token
    token = generate_token()
    expiry = datetime.now() + timedelta(hours=settings.auth_token_expire_hours)
    active_tokens[token] = expiry

    # Clean up expired tokens
    cleanup_expired_tokens()

    logger.info("Successful login, token generated")

    return LoginResponse(
        success=True,
        token=token,
        message="Login successful"
    )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout and invalidate token."""
    if credentials and credentials.credentials in active_tokens:
        del active_tokens[credentials.credentials]
        logger.info("Token invalidated on logout")

    return {"message": "Logged out successfully"}


@router.get("/status")
async def auth_status():
    """Check if authentication is required."""
    return {
        "auth_required": is_auth_enabled(),
        "active_sessions": len(active_tokens) if is_auth_enabled() else 0
    }


@router.get("/verify")
async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify if current token is valid."""
    if not is_auth_enabled():
        return {"valid": True, "auth_required": False}

    if credentials is None:
        return {"valid": False, "auth_required": True}

    token = credentials.credentials
    is_valid = verify_token(token)

    return {"valid": is_valid, "auth_required": True}


def cleanup_expired_tokens():
    """Remove expired tokens from memory."""
    now = datetime.now()
    expired = [token for token, expiry in active_tokens.items() if now > expiry]
    for token in expired:
        del active_tokens[token]
    if expired:
        logger.debug(f"Cleaned up {len(expired)} expired tokens")
