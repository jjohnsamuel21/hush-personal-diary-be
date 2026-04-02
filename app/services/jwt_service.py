from datetime import datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt


_SUBJECT_KEY = "sub"
_EXPIRY_KEY = "exp"


def create_access_token(
    user_id: str,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> str:
    """Create a signed JWT that encodes the given user_id in the ``sub`` claim.

    Args:
        user_id: The user's UUID string.
        secret: HMAC secret (or RSA/EC key material for asymmetric algorithms).
        algorithm: jose algorithm identifier, e.g. ``"HS256"``.
        expire_days: How many days until the token expires.

    Returns:
        A compact serialized JWT string.
    """
    expire = datetime.utcnow() + timedelta(days=expire_days)
    payload = {
        _SUBJECT_KEY: user_id,
        _EXPIRY_KEY: expire,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret: str,
    algorithm: str,
) -> str:
    """Decode and verify a JWT, returning the user_id stored in ``sub``.

    Args:
        token: Compact serialized JWT string.
        secret: Secret used to verify the signature.
        algorithm: Algorithm used to sign the token.

    Returns:
        The ``sub`` claim value (user UUID string).

    Raises:
        HTTPException 401: If the token is expired, has an invalid signature,
            is malformed, or is missing the ``sub`` claim.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise credentials_exception from exc

    user_id: str | None = payload.get(_SUBJECT_KEY)
    if not user_id:
        raise credentials_exception

    return user_id
