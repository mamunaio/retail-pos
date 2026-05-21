"""Service for logging user activities."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from retail_pos.models.activity_log import ActivityLog, ActivityType
from retail_pos.utils.logging import get_logger

logger = get_logger(__name__)


class ActivityService:
    """Service for logging and retrieving activity logs."""

    @staticmethod
    def log_activity(
        db: Session,
        activity_type: ActivityType,
        description: str,
        user_id: str | None = None,
        terminal_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ActivityLog:
        """Log an activity.

        Args:
            db: Database session
            activity_type: Type of activity
            description: Human-readable description
            user_id: User who performed the action
            terminal_id: Terminal where action was performed
            resource_type: Type of resource affected
            resource_id: ID of affected resource
            metadata: Additional data as dict
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            Created ActivityLog instance
        """
        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize metadata: {e}")

        activity = ActivityLog(
            activity_type=activity_type,
            user_id=user_id,
            terminal_id=terminal_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            extra_data=metadata_json,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(activity)
        db.flush()

        logger.info(
            f"Activity logged: {activity_type} by user={user_id} - {description}"
        )

        return activity

    @staticmethod
    def get_user_activities(
        db: Session, user_id: str, limit: int = 50
    ) -> list[ActivityLog]:
        """Get recent activities for a user."""
        from sqlalchemy import select

        return list(
            db.scalars(
                select(ActivityLog)
                .where(ActivityLog.user_id == user_id)
                .order_by(ActivityLog.created_at.desc())
                .limit(limit)
            ).all()
        )

    @staticmethod
    def get_resource_activities(
        db: Session, resource_type: str, resource_id: str, limit: int = 50
    ) -> list[ActivityLog]:
        """Get activities related to a specific resource."""
        from sqlalchemy import select

        return list(
            db.scalars(
                select(ActivityLog)
                .where(
                    ActivityLog.resource_type == resource_type,
                    ActivityLog.resource_id == resource_id,
                )
                .order_by(ActivityLog.created_at.desc())
                .limit(limit)
            ).all()
        )

    @staticmethod
    def get_recent_activities(
        db: Session, activity_type: ActivityType | None = None, limit: int = 100
    ) -> list[ActivityLog]:
        """Get recent activities, optionally filtered by type."""
        from sqlalchemy import select

        query = select(ActivityLog)

        if activity_type:
            query = query.where(ActivityLog.activity_type == activity_type)

        query = query.order_by(ActivityLog.created_at.desc()).limit(limit)

        return list(db.scalars(query).all())
