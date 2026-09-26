from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # bcrypt only uses the first 72 bytes; enforce the bound explicitly.
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    roles: list[str]
    auth_providers: list[str]


class ConnectedAccount(BaseModel):
    provider: str
    connected: bool
    scopes: list[str] = []
    status: str
