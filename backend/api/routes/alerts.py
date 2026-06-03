"""
Alert subscription and preference management routes.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from utils.db import (
    get_user_by_email,
    insert_alert_user,
    insert_alert_preference,
    get_alert_preference_by_id,
    update_alert_preference,
    update_user_telegram_chat_id,
    set_preferences_active_by_email,
    delete_alert_preference,
    delete_alert_user_by_id,
    delete_alert_user_by_email,
    get_active_alert_users,
    get_user_preferences_count,
    get_notification_history_by_email,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class SubscribeRequest(BaseModel):
    email: EmailStr
    telegram_chat_id: Optional[str] = None
    role: str
    location: str
    keywords: Optional[str] = None


class UpdatePreferenceRequest(BaseModel):
    role: str
    location: str
    keywords: Optional[str] = None


class TelegramUpdateRequest(BaseModel):
    email: EmailStr
    telegram_chat_id: str


class ToggleRequest(BaseModel):
    email: EmailStr
    active: bool


def _expiry_date() -> str:
    return (datetime.utcnow() + timedelta(days=30)).isoformat()


@router.post("/subscribe")
async def subscribe(request: SubscribeRequest) -> JSONResponse:
    """Subscribe a user to job alerts and create a new preference."""
    try:
        user = get_user_by_email(request.email)
        if user is None:
            user_id = insert_alert_user(request.email, request.telegram_chat_id, None)
        else:
            user_id = user["id"]

        expires_at = _expiry_date()
        preference_id = insert_alert_preference(
            user_id=user_id,
            role=request.role,
            location=request.location,
            keywords=request.keywords,
            alert_enabled=1,
            expires_at=expires_at,
        )

        return JSONResponse(
            status_code=201,
            content={
                "user_id": user_id,
                "preference_id": preference_id,
                "message": "Subscription created successfully",
            }
        )

    except Exception as exc:
        logger.error("Error subscribing user %s: %s", request.email, exc)
        raise HTTPException(status_code=500, detail="Error creating alert subscription")


@router.put("/preferences/{pref_id}")
async def update_preference(pref_id: int, request: UpdatePreferenceRequest) -> JSONResponse:
    """Update an existing alert preference and reset its expiry."""
    preference = get_alert_preference_by_id(pref_id)
    if not preference:
        raise HTTPException(status_code=404, detail="Preference not found")

    try:
        expires_at = _expiry_date()
        update_alert_preference(pref_id, request.role, request.location, request.keywords, expires_at)
        updated = get_alert_preference_by_id(pref_id)
        return JSONResponse(status_code=200, content={"preference": updated})

    except Exception as exc:
        logger.error("Error updating preference %s: %s", pref_id, exc)
        raise HTTPException(status_code=500, detail="Error updating preference")


@router.patch("/telegram")
async def update_telegram(request: TelegramUpdateRequest) -> JSONResponse:
    """Update a user's Telegram chat ID."""
    try:
        success = update_user_telegram_chat_id(request.email, request.telegram_chat_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return JSONResponse(
            status_code=200,
            content={"message": "Telegram settings updated successfully"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating Telegram chat ID for %s: %s", request.email, exc)
        raise HTTPException(status_code=500, detail="Error updating Telegram settings")


@router.patch("/toggle")
async def toggle_preferences(request: ToggleRequest) -> JSONResponse:
    """Enable or disable all preferences for a user."""
    try:
        updated = set_preferences_active_by_email(request.email, request.active)
        if updated == 0:
            raise HTTPException(status_code=404, detail="User not found or no preferences available")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Preference activity updated successfully",
                "active": request.active,
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error toggling preferences for %s: %s", request.email, exc)
        raise HTTPException(status_code=500, detail="Error updating preference activity")


@router.delete("/preferences/{pref_id}")
async def delete_preference(pref_id: int) -> JSONResponse:
    """Delete a preference and remove the user if no preferences remain."""
    user_id = delete_alert_preference(pref_id)
    if user_id == 0:
        raise HTTPException(status_code=404, detail="Preference not found")

    try:
        if get_user_preferences_count(user_id) == 0:
            delete_alert_user_by_id(user_id)

        return JSONResponse(
            status_code=200,
            content={"message": "Preference deleted successfully"}
        )

    except Exception as exc:
        logger.error("Error deleting preference %s: %s", pref_id, exc)
        raise HTTPException(status_code=500, detail="Error deleting preference")


@router.delete("/unsubscribe")
async def unsubscribe(email: EmailStr = Query(..., description="Email address to unsubscribe")) -> JSONResponse:
    """Unsubscribe a user entirely by deleting their alert account."""
    try:
        deleted = delete_alert_user_by_email(email)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="User not found")

        return JSONResponse(
            status_code=200,
            content={"message": "Unsubscribed successfully"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error unsubscribing user %s: %s", email, exc)
        raise HTTPException(status_code=500, detail="Error unsubscribing user")


@router.get("/active-users")
async def get_active_users() -> JSONResponse:
    """Retrieve users with active alert preferences."""
    try:
        users = get_active_alert_users()
        return JSONResponse(status_code=200, content={"users": users, "count": len(users)})

    except Exception as exc:
        logger.error("Error retrieving active alert users: %s", exc)
        raise HTTPException(status_code=500, detail="Error retrieving active alert users")


@router.get("/history")
async def get_history(email: EmailStr = Query(..., description="Email address to query history")) -> JSONResponse:
    """Retrieve the latest notification history for a user."""
    try:
        history = get_notification_history_by_email(email, limit=50)
        return JSONResponse(status_code=200, content={"history": history})

    except Exception as exc:
        logger.error("Error retrieving history for %s: %s", email, exc)
        raise HTTPException(status_code=500, detail="Error retrieving notification history")
