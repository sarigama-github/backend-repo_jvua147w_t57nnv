"""
Database Schemas for Localprint

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    city: str = Field(..., description="City or neighborhood (e.g., Amsterdam, Rotterdam)")
    is_active: bool = Field(True, description="Whether user is active")

class Provider(BaseModel):
    """
    People who offer their home printer for neighbors
    Collection name: "provider"
    """
    display_name: str = Field(..., description="Public name shown to neighbors")
    city: str = Field(..., description="City or neighborhood text for simple location search")
    description: Optional[str] = Field(None, description="Short description about the printer")
    price_per_page: float = Field(..., ge=0, description="Base price per page in EUR")
    color_supported: bool = Field(True, description="Can print in color")
    duplex: bool = Field(True, description="Supports duplex printing")
    rating: float = Field(0.0, ge=0, le=5, description="Average rating")
    reviews_count: int = Field(0, ge=0, description="Number of reviews")

class Review(BaseModel):
    """
    Reviews left by users for providers
    Collection name: "review"
    """
    provider_id: str = Field(..., description="ID of the reviewed provider")
    reviewer_name: str = Field(..., description="Display name of reviewer")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    comment: Optional[str] = Field(None, description="Optional comment")

class PrintRequest(BaseModel):
    """
    A lightweight request to contact a provider for a print job
    Collection name: "printrequest"
    """
    provider_id: str = Field(...)
    requester_name: str = Field(...)
    requester_email: EmailStr = Field(...)
    pages: int = Field(..., ge=1)
    color: Literal["bw", "color"] = Field("bw")
    notes: Optional[str] = None
