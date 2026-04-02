import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NoteShare(Base):
    __tablename__ = "note_shares"

    __table_args__ = (
        UniqueConstraint("note_id", "shared_with_email", name="uq_note_share_email"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    note_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shared_notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_with_email: Mapped[str] = mapped_column(String(320), nullable=False)
    shared_with_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # "view" | "edit"
    permission: Mapped[str] = mapped_column(String(20), nullable=False, default="edit")
    # "pending" | "accepted" | "declined"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    note: Mapped["SharedNote"] = relationship(  # noqa: F821
        "SharedNote",
        back_populates="shares",
        lazy="selectin",
    )
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[owner_id],
        back_populates="shares_sent",
        lazy="selectin",
    )
    shared_with_user: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[shared_with_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<NoteShare id={self.id!r} note_id={self.note_id!r} "
            f"email={self.shared_with_email!r} status={self.status!r}>"
        )
