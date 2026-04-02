import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SharedNote(Base):
    __tablename__ = "shared_notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Plaintext body — this is the shared layer; private diary entries are
    # AES-256-GCM encrypted on-device and never sent to the server.
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    font_family: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Merriweather"
    )
    cover_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#5C6BC0"
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="owned_notes",
        lazy="selectin",
    )
    shares: Mapped[list["NoteShare"]] = relationship(  # noqa: F821
        "NoteShare",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SharedNote id={self.id!r} title={self.title!r}>"
