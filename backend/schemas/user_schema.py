"""This schema layer is responsible for API validation, not database storage."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """
    Schema used when creating a new BuyQK user.
    """

    # Customer's full name
    name: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    # Customer's email address
    email: EmailStr

    # Customer's phone number
    phone: str = Field(
        ...,
        min_length=10,
        max_length=20
    )

    # Plain-text password.
    # It will be hashed before being stored in the database.
    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )

    # Preferred conversation language
    language: str = Field(
        default="English",
        max_length=20
    )


class UserResponse(BaseModel):
    """
    Schema returned by the API after retrieving a user.

    Sensitive fields such as password_hash are intentionally
    excluded.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Database user ID
    id: int

    # Customer's full name
    name: str

    # Customer's email
    email: EmailStr

    # Customer's phone number
    phone: str

    # Preferred conversation language
    language: str

    # Account creation timestamp
    created_at: datetime

    # Account last-update timestamp
    updated_at: datetime