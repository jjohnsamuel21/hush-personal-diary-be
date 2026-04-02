from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AuthResponse, GoogleAuthRequest, UserOut
from app.services.google_auth import verify_google_token
from app.services.jwt_service import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


@router.post("/google", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def google_auth(
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Exchange a Google ID token for a Hush session JWT.

    - Verifies the token with Google's public keys.
    - Upserts the user record (creates on first sign-in, updates on subsequent).
    - Returns a signed JWT plus the UserOut payload.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google client ID is not configured on the server.",
        )

    payload = verify_google_token(body.google_id_token, settings.google_client_id)

    google_sub: str = payload["sub"]
    email: str = payload.get("email", "")
    display_name: str | None = payload.get("name")
    avatar_url: str | None = payload.get("picture")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account does not have a verified email address.",
        )

    # Try to find an existing user by their stable Google subject ID.
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        # First sign-in — create a new user record.
        user = User(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
        await db.flush()  # populate user.id without committing yet
    else:
        # Subsequent sign-in — refresh mutable profile fields.
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url
        user.updated_at = datetime.utcnow()

    # Session commit is handled by get_db() on context-manager exit.
    await db.flush()

    access_token = create_access_token(
        user_id=user.id,
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_days=settings.jwt_expire_days,
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=_user_to_out(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the profile of the currently authenticated user."""
    return _user_to_out(current_user)


@router.delete("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)) -> None:
    """Log out the current user.

    JWTs are stateless, so this endpoint exists primarily as a client-facing
    contract.  The client should discard the token on receipt of 204.
    """
    return None
