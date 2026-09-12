"""Helpers for converting a scheme record into a searchable plain-text document."""
from __future__ import annotations

from backend.rules import describe_rules


def build_scheme_document(scheme: dict) -> str:
    """
    Build the curated text used for embedding generation and retrieval.

    Deliberately excludes: id (opaque, no semantic value), official_url,
    apply_mode (procedural, not about *who the scheme is for*), and the raw
    documents list (nearly every scheme requires "Aadhaar card" + "Bank
    passbook" -- including it dilutes distinctiveness rather than adding it).

    Eligibility is rendered via describe_rules() -- the SAME function your
    scheme detail page uses -- so "max_income: 350000" becomes "Annual
    family income up to ₹3,50,000", which an embedding model can actually
    relate to a phrase like "low income" in a user's free-text note.
    """
    sections: list[str] = []

    if scheme.get("name"):
        sections.append(scheme["name"])

    if scheme.get("description"):
        sections.append(scheme["description"])

    if scheme.get("benefit"):
        sections.append(f"Benefit: {scheme['benefit']}")

    if scheme.get("category"):
        sections.append(f"Category: {scheme['category']}")

    state = scheme.get("state")
    if state and state != "ALL":
        sections.append(f"State: {state}")
    else:
        sections.append("Applicable nationwide (central government scheme)")

    rules = scheme.get("rules") or {}
    if rules:
        criteria = describe_rules(rules)
        if criteria:
            sections.append("Eligibility: " + "; ".join(criteria))

    return "\n".join(sections)