"""
This file will:
Validate required address fields.
Validate postal/PIN code format.
Validate optional latitude/longitude.
Accept is_default when creating an address.
Return database address records safely through the API.
Keep the schema separate from the SQLAlchemy Address model.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AddressCreate(BaseModel):
    """
    Schema used when creating a new customer address.
    """

    # First line of the address
    address_line_1: str = Field(
        ...,
        min_length=3,
        max_length=255
    )

    # Optional second line of the address
    address_line_2: str | None = Field(
        default=None,
        max_length=255
    )

    # City
    city: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    # State
    state: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    # Postal/PIN code
    postal_code: str = Field(
        ...,
        min_length=4,
        max_length=20
    )

    # Optional latitude
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90
    )

    # Optional longitude
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180
    )

    # Whether this should become the user's default address
    is_default: bool = False


class AddressResponse(BaseModel):
    """
    Schema returned by the API when an address is retrieved.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Database address ID
    id: int

    # User who owns the address
    user_id: int

    # Address fields
    address_line_1: str
    address_line_2: str | None

    city: str
    state: str
    postal_code: str

    # Location information
    latitude: float | None
    longitude: float | None

    # Default-address flag
    is_default: bool

    # Timestamps
    created_at: datetime