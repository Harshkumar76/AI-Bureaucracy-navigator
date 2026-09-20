"""Models for AI Bureaucracy Navigator.

Pydantic models used for request/response validation. Scheme records are
stored as plain PostgreSQL rows (see backend/database.py) — no ORM layer.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    residence: Optional[str] = None
    annual_income: Optional[int] = None
    category: Optional[str] = None
    religion: Optional[str] = None
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    marital_status: Optional[str] = None
    disability_pct: Optional[int] = None
    has_bpl_card: Optional[bool] = None
    owns_cultivable_land: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    has_girl_child_under_10: Optional[bool] = None

    # Additional eligibility facts
    has_bank_account: Optional[bool] = None
    has_lpg_connection: Optional[bool] = None
    income_tax_payer: Optional[bool] = None
    government_employee: Optional[bool] = None

    # NFBS
    breadwinner_deceased: Optional[bool] = None
    breadwinner_age: Optional[int] = None

    # Education / scholarship
    class_level: Optional[str] = None
    academic_percentage: Optional[float] = None
    receives_other_scholarship: Optional[bool] = None

    # Other scheme-specific facts
    artisan_trade: Optional[str] = None
    street_vendor: Optional[bool] = None
    existing_business: Optional[bool] = None

    documents_have: List[str] = Field(default_factory=list)
    extra_info: Optional[str] = None


class Finding(BaseModel):
    scheme_id: str
    name: str
    benefit: str
    status: str                                 # "eligible" | "possible" | "ineligible"
    reasons: List[str]                          # human-readable rule outcomes
    unknown_fields: List[str]                   # profile fields we'd need to confirm
    documents: List[str]
    documents_missing: List[str]
    official_url: str
    apply_mode: str
    last_verified: str
    link_alive: Optional[bool] = None           # set by Verification Agent when live-checking