from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.jwt_service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that resolves the Bearer JWT to a User ORM object.

    Raises:
        HTTPException 401: If the token is invalid or the user no longer exists
            in the database.
    """
    user_id = decode_access_token(
        token,
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
