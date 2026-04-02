from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.schemas.auth import UserOut


class SharedNoteCreate(BaseModel):
    title: str = ""
    body: str = ""
    font_family: str = "Merriweather"
    cover_color: str = "#5C6BC0"


class SharedNoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    font_family: Optional[str] = None
    cover_color: Optional[str] = None
    is_archived: Optional[bool] = None


class CollaboratorInfo(BaseModel):
    share_id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    permission: str
    status: str


class SharedNoteOut(BaseModel):
    id: str
    title: str
    body: str
    font_family: str
    cover_color: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    owner: UserOut
    collaborators: list[CollaboratorInfo]
    my_permission: str


class ShareRequest(BaseModel):
    emails: list[str]
    permission: str = "edit"

    @field_validator("permission")
    @classmethod
    def permission_must_be_valid(cls, v: str) -> str:
        if v not in ("view", "edit"):
            raise ValueError("permission must be 'view' or 'edit'")
        return v

    @field_validator("emails")
    @classmethod
    def emails_must_not_be_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("emails list must not be empty")
        return [e.strip().lower() for e in v if e.strip()]


class InviteOut(BaseModel):
    share_id: str
    note_id: str
    note_title: str
    shared_by_email: str
    shared_by_name: Optional[str] = None
    permission: str
    created_at: datetime
