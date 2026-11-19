"""Authentication-related Pydantic models."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from .user import Role, UserPublic, validate_new_password


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="E-mail institucional")
    password: str = Field(..., min_length=6, description="Senha do usuário")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_new_password(value)
