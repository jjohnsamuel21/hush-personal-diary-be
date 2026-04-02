from pydantic import BaseModel, EmailStr


class GoogleAuthRequest(BaseModel):
    google_id_token: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
