"""Append-only audit trail (spec §5, §24).

Every state-changing action is recorded with timestamp, user, what was
changed, and optionally the caller's IP/user-agent. The table is treated
as append-only: never UPDATE or DELETE audit rows.
"""

from sqlalchemy.orm import Session

from app.models.user import AuditLog


def log_action(
    db: Session,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Add an audit row and flush it (caller commits the transaction)."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    db.flush()
    return entry
