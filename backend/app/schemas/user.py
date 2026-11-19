from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["admin", "gestor", "professor", "aluno"]


def validate_new_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("A senha deve ter no máximo 72 bytes UTF-8")
    if value.lower() in {"1234567890", "123456789012", "password123", "senha12345", "qwerty12345"}:
        raise ValueError("Escolha uma senha menos comum")
    return value


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="E-mail institucional único")
    full_name: str = Field(..., min_length=1, max_length=255, description="Nome completo do usuário")
    role: Role = Field(..., description="Perfil associado ao usuário")


class UserCreate(UserBase):
    password: str = Field(..., min_length=10, max_length=72, description="Senha em texto puro")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_new_password(value)
    school_id: Optional[int] = Field(
        default=None,
        description="ID da unidade/escola associada",
    )
    classroom_id: Optional[int] = Field(
        default=None, description="ID da turma do usuário (quando aplicável)"
    )
    teachable_subject_ids: Optional[list[int]] = Field(
        default=None,
        description="Lista de matérias que o professor pode lecionar",
    )

    @field_validator("school_id", "classroom_id", mode="before")
    @classmethod
    def _normalize_optional_fk(cls, value: Optional[int | str]) -> Optional[int]:
        """
        Aceita valores enviados como string, números ou vazios
        e converte para inteiro ou None quando apropriado.
        """
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return None
            lowered = stripped.lower()
            if lowered in {"null", "none", "undefined"}:
                return None
            value = stripped
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @field_validator("teachable_subject_ids", mode="before")
    @classmethod
    def _normalize_subject_list(cls, value):
        if value in (None, "", [], ()):
            return None
        if isinstance(value, str):
            value = [value]
        normalized = []
        for item in value:
            if item in (None, "", "null", "undefined"):
                continue
            try:
                normalized.append(int(item))
            except (TypeError, ValueError):
                continue
        return normalized or None


class UserRecipient(BaseModel):
    id: str
    full_name: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


class UserPublic(UserBase):
    id: str
    must_change_password: bool = False
    school_id: Optional[int] = None
    classroom_id: Optional[int] = None
    teachable_subject_ids: list[int] = Field(
        default_factory=list,
        description="IDs das matérias habilitadas para o professor",
    )

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    password: Optional[str] = Field(default=None, min_length=10, max_length=72)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: Optional[str]) -> Optional[str]:
        return validate_new_password(value) if value is not None else None
    school_id: Optional[int] = None
    classroom_id: Optional[int] = None
    teachable_subject_ids: Optional[list[int]] = None

    @field_validator("school_id", "classroom_id", mode="before")
    @classmethod
    def _normalize_optional_fk(cls, value: Optional[int | str]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return None
            lowered = stripped.lower()
            if lowered in {"null", "none", "undefined"}:
                return None
            value = stripped
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @field_validator("teachable_subject_ids", mode="before")
    @classmethod
    def _normalize_subject_list(cls, value):
        if value in (None, "", [], ()):
            return None
        if isinstance(value, str):
            value = [value]
        normalized = []
        for item in value:
            if item in (None, "", "null", "undefined"):
                continue
            try:
                normalized.append(int(item))
            except (TypeError, ValueError):
                continue
        return normalized or None
