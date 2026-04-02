from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.note_share import NoteShare
from app.models.shared_note import SharedNote
from app.models.user import User
from app.schemas.note import InviteOut

router = APIRouter(prefix="/api/invites", tags=["invites"])


@router.get("", response_model=list[InviteOut])
async def list_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InviteOut]:
    """Return all pending invites addressed to the current user's email.

    As a side effect, any invite that has not yet been linked to a user account
    (``shared_with_id`` is NULL) is auto-linked to the current user now that
    they are authenticated.
    """
    result = await db.execute(
        select(NoteShare)
        .options(
            selectinload(NoteShare.note).selectinload(SharedNote.owner),
            selectinload(NoteShare.owner),
        )
        .where(
            NoteShare.shared_with_email == current_user.email,
            NoteShare.status == "pending",
        )
        .order_by(NoteShare.created_at.desc())
    )
    shares = result.scalars().all()

    invites: list[InviteOut] = []
    for share in shares:
        # Auto-link the user account if not already done.
        if share.shared_with_id is None:
            share.shared_with_id = current_user.id
            # No explicit flush needed; get_db commits on exit.

        invites.append(
            InviteOut(
                share_id=share.id,
                note_id=share.note_id,
                note_title=share.note.title,
                shared_by_email=share.owner.email,
                shared_by_name=share.owner.display_name,
                permission=share.permission,
                created_at=share.created_at,
            )
        )

    return invites


@router.post("/{share_id}/accept", status_code=status.HTTP_200_OK)
async def accept_invite(
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept a pending invite.

    Sets ``status`` to ``"accepted"`` and ensures ``shared_with_id`` is linked.
    """
    share = await _get_own_invite(share_id, current_user, db)
    if share.status == "accepted":
        return {"detail": "Invite already accepted."}

    share.status = "accepted"
    share.shared_with_id = current_user.id
    await db.flush()

    return {"detail": "Invite accepted."}


@router.post("/{share_id}/decline", status_code=status.HTTP_200_OK)
async def decline_invite(
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Decline a pending invite, setting ``status`` to ``"declined"``."""
    share = await _get_own_invite(share_id, current_user, db)
    if share.status == "declined":
        return {"detail": "Invite already declined."}

    share.status = "declined"
    share.shared_with_id = current_user.id
    await db.flush()

    return {"detail": "Invite declined."}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_own_invite(
    share_id: str,
    current_user: User,
    db: AsyncSession,
) -> NoteShare:
    """Load a NoteShare and verify it belongs to the current user.

    Raises:
        HTTPException 404: Share record not found.
        HTTPException 403: The share is addressed to a different email.
    """
    result = await db.execute(
        select(NoteShare).where(NoteShare.id == share_id)
    )
    share = result.scalar_one_or_none()

    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found.",
        )

    if share.shared_with_email != current_user.email and share.shared_with_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invite does not belong to you.",
        )

    return share
