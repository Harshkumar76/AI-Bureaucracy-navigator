"""Models for AI Bureaucracy Navigator.

- Pydantic models: used for request/response validation
- SQLAlchemy models: used for PostgreSQL storage
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base

# ============================================================
# Pydantic models (unchanged, used in API)
# ============================================================

class UserProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None                # "male" | "female" | "other"
    state: Optional[str] = None
    residence: Optional[str] = None             # "rural" | "urban"
    annual_income: Optional[int] = None         # family income in INR
    category: Optional[str] = None              # "General" | "OBC" | "SC" | "ST" | "EWS"
    religion: Optional[str] = None
    occupation: Optional[str] = None            # "student" | "farmer" | "salaried" | ...
    education_level: Optional[str] = None       # "below_10th" | "10th_pass" | "12th_pass" | "ug" | "pg" | "not_studying"
    marital_status: Optional[str] = None        # "single" | "married" | "widowed" | "divorced"
    disability_pct: Optional[int] = None
    has_bpl_card: Optional[bool] = None
    owns_cultivable_land: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    has_girl_child_under_10: Optional[bool] = None
    documents_have: List[str] = Field(default_factory=list)
    extra_info: Optional[str] = None            # free-text box, mined by the intake step


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

# ============================================================
# SQLAlchemy models (NEW, used for PostgreSQL storage)
# ============================================================

class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    level = Column(String, nullable=True)
    benefit = Column(Text, nullable=True)
    official_url = Column(String, nullable=True)
    last_verified = Column(DateTime, nullable=True)

    # Rules stored as JSON (same as in schemes.json)
    rules = Column(JSONB, nullable=True)
