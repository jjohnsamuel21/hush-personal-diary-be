import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, exists
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.note_share import NoteShare
from app.models.shared_note import SharedNote
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.note import (
    CollaboratorInfo,
    ShareRequest,
    SharedNoteCreate,
    SharedNoteOut,
    SharedNoteUpdate,
)

router = APIRouter(prefix="/api/notes", tags=["notes"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


def _build_note_out(note: SharedNote, current_user: User) -> SharedNoteOut:
    """Construct a SharedNoteOut from an ORM object without model_validate."""
    is_owner = note.owner_id == current_user.id

    collaborators: list[CollaboratorInfo] = []
    for share in note.shares:
        collaborators.append(
            CollaboratorInfo(
                share_id=share.id,
                email=share.shared_with_email,
                display_name=share.shared_with_user.display_name if share.shared_with_user else None,
                avatar_url=share.shared_with_user.avatar_url if share.shared_with_user else None,
                permission=share.permission,
                status=share.status,
            )
        )

    if is_owner:
        my_permission = "owner"
    else:
        # Find the share row that belongs to this user.
        my_permission = "view"
        for share in note.shares:
            if (
                share.shared_with_email == current_user.email
                or share.shared_with_id == current_user.id
            ):
                my_permission = share.permission
                break

    return SharedNoteOut(
        id=note.id,
        title=note.title,
        body=note.body,
        font_family=note.font_family,
        cover_color=note.cover_color,
        is_archived=note.is_archived,
        created_at=note.created_at,
        updated_at=note.updated_at,
        owner=_user_to_out(note.owner),
        collaborators=collaborators,
        my_permission=my_permission,
    )


async def _get_note_with_access(
    note_id: str,
    current_user: User,
    db: AsyncSession,
    *,
    require_owner: bool = False,
    require_edit: bool = False,
) -> SharedNote:
    """Load a note and verify the current user has the required access level.

    Args:
        note_id: The note UUID string.
        current_user: The authenticated user making the request.
        db: Async database session.
        require_owner: If True, raises 403 unless the user owns the note.
        require_edit: If True, raises 403 unless the user can edit (owner or
            accepted editor).

    Returns:
        The SharedNote ORM object with relationships eagerly loaded.

    Raises:
        HTTPException 404: Note does not exist.
        HTTPException 403: User lacks the required permission.
    """
    result = await db.execute(
        select(SharedNote)
        .options(
            selectinload(SharedNote.owner),
            selectinload(SharedNote.shares).selectinload(NoteShare.shared_with_user),
        )
        .where(SharedNote.id == note_id)
    )
    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")

    is_owner = note.owner_id == current_user.id

    if require_owner and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the note owner can perform this action.")

    if not is_owner:
        # Check for an accepted share.
        accepted_share = next(
            (
                s for s in note.shares
                if (
                    s.shared_with_email == current_user.email
                    or s.shared_with_id == current_user.id
                )
                and s.status == "accepted"
            ),
            None,
        )
        if accepted_share is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this note.")

        if require_edit and accepted_share.permission != "edit":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have edit permission for this note.")

    return note


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[SharedNoteOut])
async def list_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SharedNoteOut]:
    """Return all notes where the user is the owner OR an accepted collaborator."""
    # Subquery: notes shared with the current user (accepted).
    shared_subquery = (
        select(NoteShare.note_id)
        .where(
            or_(
                NoteShare.shared_with_email == current_user.email,
                NoteShare.shared_with_id == current_user.id,
            ),
            NoteShare.status == "accepted",
        )
        .scalar_subquery()
    )

    result = await db.execute(
        select(SharedNote)
        .options(
            selectinload(SharedNote.owner),
            selectinload(SharedNote.shares).selectinload(NoteShare.shared_with_user),
        )
        .where(
            or_(
                SharedNote.owner_id == current_user.id,
                SharedNote.id.in_(shared_subquery),
            )
        )
        .order_by(SharedNote.updated_at.desc())
    )
    notes = result.scalars().all()
    return [_build_note_out(note, current_user) for note in notes]


@router.post("", response_model=SharedNoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: SharedNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedNoteOut:
    """Create a new shared note owned by the current user."""
    note = SharedNote(
        owner_id=current_user.id,
        title=body.title,
        body=body.body,
        font_family=body.font_family,
        cover_color=body.cover_color,
    )
    db.add(note)
    await db.flush()

    # Re-load with relationships to build the response.
    result = await db.execute(
        select(SharedNote)
        .options(
            selectinload(SharedNote.owner),
            selectinload(SharedNote.shares).selectinload(NoteShare.shared_with_user),
        )
        .where(SharedNote.id == note.id)
    )
    note = result.scalar_one()
    return _build_note_out(note, current_user)


@router.get("/{note_id}", response_model=SharedNoteOut)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedNoteOut:
    """Return a single note. Requires owner or accepted collaborator."""
    note = await _get_note_with_access(note_id, current_user, db)
    return _build_note_out(note, current_user)


@router.put("/{note_id}", response_model=SharedNoteOut)
async def update_note(
    note_id: str,
    body: SharedNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedNoteOut:
    """Update a note. Requires owner or accepted editor."""
    note = await _get_note_with_access(note_id, current_user, db, require_edit=True)

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    note.updated_at = datetime.utcnow()

    await db.flush()

    result = await db.execute(
        select(SharedNote)
        .options(
            selectinload(SharedNote.owner),
            selectinload(SharedNote.shares).selectinload(NoteShare.shared_with_user),
        )
        .where(SharedNote.id == note.id)
    )
    note = result.scalar_one()
    return _build_note_out(note, current_user)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a note. Owner only."""
    note = await _get_note_with_access(note_id, current_user, db, require_owner=True)
    await db.delete(note)
    await db.flush()


@router.post("/{note_id}/share", response_model=list[CollaboratorInfo], status_code=status.HTTP_201_CREATED)
async def share_note(
    note_id: str,
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollaboratorInfo]:
    """Share a note with one or more email addresses. Owner only.

    Idempotent: if a share for a given email already exists on this note the
    existing record is returned rather than raising an error.
    """
    print(note_id, body, current_user.email, db)
    note = await _get_note_with_access(note_id, current_user, db, require_owner=True)

    results: list[CollaboratorInfo] = []

    for email in body.emails:
        email = email.strip().lower()
        if email == current_user.email.lower():
            # Cannot share with yourself.
            continue

        # Check if a share already exists for this email.
        existing_result = await db.execute(
            select(NoteShare).where(
                NoteShare.note_id == note_id,
                NoteShare.shared_with_email == email,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            # Update permission if it changed.
            existing.permission = body.permission
            share = existing
        else:
            # Resolve to a user account if one exists.
            user_result = await db.execute(select(User).where(User.email == email))
            target_user = user_result.scalar_one_or_none()

            share = NoteShare(
                note_id=note_id,
                owner_id=current_user.id,
                shared_with_email=email,
                shared_with_id=target_user.id if target_user else None,
                permission=body.permission,
                status="pending",
            )
            db.add(share)

        await db.flush()

        # Reload to get shared_with_user if it was just linked.
        share_result = await db.execute(
            select(NoteShare)
            .options(selectinload(NoteShare.shared_with_user))
            .where(NoteShare.id == share.id)
        )
        share = share_result.scalar_one()

        results.append(
            CollaboratorInfo(
                share_id=share.id,
                email=share.shared_with_email,
                display_name=share.shared_with_user.display_name if share.shared_with_user else None,
                avatar_url=share.shared_with_user.avatar_url if share.shared_with_user else None,
                permission=share.permission,
                status=share.status,
            )
        )

    return results


@router.delete("/{note_id}/share/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collaborator(
    note_id: str,
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a collaborator from a note.

    The note owner can remove anyone; a collaborator can remove themselves
    (self-remove / leave the note).
    """
    share_result = await db.execute(
        select(NoteShare).where(
            NoteShare.id == share_id,
            NoteShare.note_id == note_id,
        )
    )
    share = share_result.scalar_one_or_none()

    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share record not found.")

    is_owner = share.owner_id == current_user.id
    is_self_remove = (
        share.shared_with_email == current_user.email
        or share.shared_with_id == current_user.id
    )

    if not is_owner and not is_self_remove:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner or the collaborator themselves can remove this share.",
        )

    await db.delete(share)
    await db.flush()


@router.get("/{note_id}/collaborators", response_model=list[CollaboratorInfo])
async def list_collaborators(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollaboratorInfo]:
    """List all collaborators on a note. Owner only."""
    note = await _get_note_with_access(note_id, current_user, db, require_owner=True)

    collaborators: list[CollaboratorInfo] = []
    for share in note.shares:
        collaborators.append(
            CollaboratorInfo(
                share_id=share.id,
                email=share.shared_with_email,
                display_name=share.shared_with_user.display_name if share.shared_with_user else None,
                avatar_url=share.shared_with_user.avatar_url if share.shared_with_user else None,
                permission=share.permission,
                status=share.status,
            )
        )
    return collaborators
