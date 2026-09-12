from dataclasses import dataclass

from backend.rules import evaluate


@dataclass
class Profile:
    age: int | None = None
    annual_income: int | None = None
    gender: str | None = None
    category: str | None = None
    occupation: str | None = None
    residence: str | None = None
    education_level: str | None = None
    religion: str | None = None
    disability_pct: int | None = None
    marital_status: str | None = None
    has_bpl_card: bool | None = None
    owns_cultivable_land: bool | None = None
    owns_pucca_house: bool | None = None
    has_girl_child_under_10: bool | None = None


profile = Profile(
    age=20,
    annual_income=None,
    residence="rural",
    education_level="ug",
)

rules = {
    "min_age": 18,
    "max_age": 30,
    "max_income": 250000,
    "residence": "rural",
    "education_in": ["ug", "pg"],
}

status, reasons, unknowns = evaluate(profile, rules)

print("Status:", status)

print("\nReasons:")
for reason in reasons:
    print(reason)

print("\nUnknown fields:")
print(unknowns)