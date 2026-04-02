from fastapi import HTTPException, status

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


def verify_google_token(token: str, client_id: str) -> dict:
    """Verify a Google ID token and return the decoded payload.

    Args:
        token: The raw Google ID token string sent from the client.
        client_id: The OAuth2 client ID registered in the Google Cloud Console.

    Returns:
        The decoded token payload as a dict containing at minimum:
        ``sub``, ``email``, ``name``, ``picture``.

    Raises:
        HTTPException 401: If the token is invalid, expired, or the audience
            does not match ``client_id``.
    """
    try:
        request = google_requests.Request()
        payload = google_id_token.verify_oauth2_token(
            token,
            request,
            audience=client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token verification failed.",
        ) from exc

    return payload
