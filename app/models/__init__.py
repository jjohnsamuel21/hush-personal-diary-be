# Import all models so that Alembic's autogenerate and init_db() can discover
# them through Base.metadata.
from app.models.user import User
from app.models.shared_note import SharedNote
from app.models.note_share import NoteShare

__all__ = ["User", "SharedNote", "NoteShare"]
