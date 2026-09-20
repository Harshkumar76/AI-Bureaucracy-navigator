import sys
import argparse
import json
import random
import time
from pathlib import Path
from copy import deepcopy


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from backend.database import db_connection
from backend.llm import _chat
from backend.models import UserProfile
from backend.rules import evaluate


OUTPUT_PATH = Path("eval/classifier/synthetic_dataset.jsonl")


# ---------------------------------------------------------------------
# Candidate values
# ---------------------------------------------------------------------

STATES = [
    "Uttar Pradesh",
    "Bihar",
    "Madhya Pradesh",
    "Rajasthan",
    "West Bengal",
    "Maharashtra",
    "Tamil Nadu",
    "Karnataka",
    "Telangana",
    "Odisha",
]

CATEGORIES = [
    "general",
    "obc",
    "sc",
    "st",
]

RELIGIONS = [
    "Hindu",
    "Muslim",
    "Christian",
    "Sikh",
    "Buddhist",
    "Jain",
    "Parsi",
]

GENDERS = [
    "male",
    "female",
]

RESIDENCES = [
    "rural",
    "urban",
]

OCCUPATIONS = [
    "farmer",
    "artisan",
    "street_vendor",
    "unorganised_worker",
    "agricultural_worker",
    "construction_worker",
    "domestic_worker",
    "rickshaw_driver",
    "student",
    "private_employee",
    "other",
]

ARTISAN_TRADES = [
    "carpenter",
    "blacksmith",
    "goldsmith",
    "potter",
    "sculptor",
    "mason",
    "tailor",
    "barber",
    "washerman",
    "cobbler",
]

MARITAL_STATUSES = [
    "single",
    "married",
    "widowed",
    "divorced",
]

# Keep values compatible with the actual rule engine.
EDUCATION_LEVELS = [
    "below_10th",
    "10th_pass",
    "12th_pass",
    "ug",
    "pg",
    "not_studying",
]

INCOMES = [
    5000,
    8000,
    10000,
    12000,
    15000,
    20000,
    30000,
    50000,
    75000,
    100000,
    200000,
    500000,
    900000,
]


# ---------------------------------------------------------------------
# Exact 30-scheme target order
# ---------------------------------------------------------------------

SCHEME_ORDER = [
    "pm-kisan",
    "csss",
    "post-matric-sc",
    "nmmss",
    "minority-post-matric",
    "pmay-g",
    "pm-ujjwala",
    "pmjay",
    "apy",
    "pmsby",
    "pmjjby",
    "sukanya-samriddhi",
    "pm-vishwakarma",
    "ignoaps",
    "pmkvy",
    "nfbs",
    "pmjdy",
    "pmmy",
    "pmegp",
    "pm-svanidhi",
    "pm-kusum",
    "pm-surya-ghar",
    "pmmvy",
    "pmfby",
    "pm-sym",
    "pm-kisan-maandhan",
    "pmay-u-2",
    "naps-2",
    "ddu-gky",
    "jss",
]


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def load_schemes():
    """
    Load the current schemes directly from PostgreSQL.

    The generator intentionally uses the database as the source of
    truth for scheme rules instead of duplicating rules in this file.
    """

    with db_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, data
            FROM schemes
            ORDER BY id
            """
        )

        schemes = []

        for row in cur.fetchall():
            data = row["data"] or {}

            schemes.append(
                {
                    "id": row["id"],
                    "rules": data.get("rules", {}),
                }
            )

        return schemes


# ---------------------------------------------------------------------
# Profile coherence
# ---------------------------------------------------------------------

def choose_education(age):
    """
    Produce an age-compatible education level.

    Vocabulary matches the current rule engine:
        below_10th
        10th_pass
        12th_pass
        ug
        pg
        not_studying
    """

    if age <= 15:
        return "below_10th", str(random.randint(5, 9))

    if age == 16:
        return "10th_pass", "10"

    if age == 17:
        return random.choice(
            [
                ("10th_pass", "10"),
                ("12th_pass", "11"),
                ("12th_pass", "12"),
            ]
        )

    if age <= 20:
        return random.choice(
            [
                ("12th_pass", "12"),
                ("ug", "college"),
            ]
        )

    return random.choice(
        [
            ("10th_pass", "10"),
            ("12th_pass", "12"),
            ("ug", "college"),
            ("pg", "postgraduate"),
            ("not_studying", "not_studying"),
        ]
    )


def coherent_marital_status(age):
    """
    Generate a broadly age-compatible marital status.

    This is not intended to reproduce population statistics.
    """

    if age < 18:
        return "single"

    if age < 25:
        return random.choice(
            [
                "single",
                "single",
                "married",
            ]
        )

    if age < 45:
        return random.choice(
            [
                "single",
                "married",
                "married",
            ]
        )

    return random.choice(
        [
            "married",
            "married",
            "widowed",
            "divorced",
        ]
    )


def build_profile(
    age=None,
    gender=None,
    occupation=None,
    residence=None,
    income=None,
):
    """
    Create one coherent structured citizen profile.

    The profile keys intentionally preserve the format already used
    by the classifier dataset generator.
    """

    if age is None:
        age = random.randint(14, 70)

    if gender is None:
        gender = random.choice(GENDERS)

    if occupation is None:
        occupation = random.choice(OCCUPATIONS)

    if residence is None:
        residence = random.choice(RESIDENCES)

    if income is None:
        income = random.choice(INCOMES)

    education, class_level = choose_education(age)

    profile = {
        "age": age,
        "gender": gender,
        "category": random.choice(CATEGORIES),
        "religion": random.choice(RELIGIONS),
        "education_level": education,
        "marital_status": coherent_marital_status(age),
        "occupation": occupation,
        "residence": residence,
        "state": random.choice(STATES),
        "annual_income": income,

        # Existing boolean/profile attributes.
        "has_bank_account": random.choice([True, False]),
        "has_lpg_connection": random.choice([True, False]),
        "income_tax_payer": random.choice([True, False]),
        "government_employee": random.choice([True, False]),

        # Household / eligibility attributes.
        "has_bpl_card": random.choice([True, False]),
        "owns_cultivable_land": random.choice([True, False]),
        "owns_pucca_house": random.choice([True, False]),
        "has_girl_child_under_10": random.choice([True, False]),

        # Disability.
        "disability_pct": random.choice(
            [
                0,
                0,
                0,
                40,
                50,
                60,
                80,
            ]
        ),

        # Breadwinner.
        "breadwinner_deceased": random.choice([True, False]),
        "breadwinner_age": random.randint(18, 70),

        # Education details.
        "class_level": class_level,
        "academic_percentage": round(
            random.uniform(45, 95),
            1,
        ),

        # Other profile attributes.
        "receives_other_scholarship": random.choice(
            [True, False]
        ),
        "artisan_trade": None,
        "street_vendor": False,
        "existing_business": random.choice(
            [True, False]
        ),
    }

    # -------------------------------------------------------------
    # Occupation-specific coherence
    # -------------------------------------------------------------

    if occupation == "artisan":
        profile["artisan_trade"] = random.choice(
            ARTISAN_TRADES
        )

    if occupation == "street_vendor":
        profile["street_vendor"] = True

    if occupation != "artisan":
        profile["artisan_trade"] = None

    if occupation != "street_vendor":
        profile["street_vendor"] = False

    # Children should generally not be government employees.
    if age < 18:
        profile["government_employee"] = False

    # Students should have plausible age/education combinations.
    if occupation == "student":
        if age > 30:
            profile["age"] = random.randint(15, 25)

        education, class_level = choose_education(
            profile["age"]
        )

        profile["education_level"] = education
        profile["class_level"] = class_level

        profile["government_employee"] = False

    return profile


# ---------------------------------------------------------------------
# Synthetic classifier ground truth
# ---------------------------------------------------------------------

def get_synthetic_rules(rules):
    """
    Return rules usable for synthetic classifier ground truth.

    External verification is excluded because it cannot be observed
    from a generated profile.

    Returns None when the scheme has no remaining
    profile-observable eligibility rules.
    """

    synthetic_rules = deepcopy(rules)

    synthetic_rules.pop(
        "requires_external_verification",
        None,
    )

    if "category_in" in synthetic_rules:
        synthetic_rules["category_in"] = [
            str(category).strip().lower()
            for category in synthetic_rules["category_in"]
        ]

    # No observable rules remain.
    if not synthetic_rules:
        return None

    return synthetic_rules


def get_labels(profile, schemes):
    """
    Generate synthetic classifier labels.

    A label means:

        "This profile satisfies all deterministic,
         profile-observable rules for this scheme."

    External verification is deliberately excluded from the
    synthetic ground truth because it cannot be determined from
    the generated profile alone.

    The production eligibility engine remains unchanged.
    """

    user_profile = UserProfile(**profile)

    labels = []

    for scheme in schemes:
        synthetic_rules = get_synthetic_rules(
            scheme["rules"]
        )
        
        if synthetic_rules is None:
           continue

        status, _, _ = evaluate(
            user_profile,
            synthetic_rules,
        )

        if status == "eligible":
            labels.append(scheme["id"])

    return labels


# ---------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------

def choose_value_from_list(
    expected,
    available,
):
    """
    Pick one value from expected that is compatible with our
    synthetic candidate vocabulary.
    """

    if not expected:
        return None

    compatible = [
        value
        for value in expected
        if value in available
    ]

    if compatible:
        return random.choice(compatible)

    return random.choice(expected)


def apply_rule_hints(profile, rules):
    """
    Construct a profile that satisfies the deterministic rules.

    Only fields already represented by UserProfile/rules are changed.

    External verification is deliberately ignored here because it
    cannot be satisfied from synthetic profile information.
    """

    # -------------------------------------------------------------
    # Age
    # -------------------------------------------------------------

    min_age = rules.get("min_age")
    max_age = rules.get("max_age")

    if min_age is not None and max_age is not None:

        min_age = int(min_age)
        max_age = int(max_age)

        if min_age > max_age:
            raise ValueError(
                f"Impossible age range: {min_age}>{max_age}"
            )

        profile["age"] = random.randint(
            min_age,
            max_age,
        )

    elif min_age is not None:

        min_age = int(min_age)

        # Keep generated ages within a realistic range.
        profile["age"] = random.randint(
            max(14, min_age),
            max(14, min_age + 15),
        )

    elif max_age is not None:

        max_age = int(max_age)

        if max_age < 14:
            raise ValueError(
                f"Scheme has unsupported maximum age: {max_age}"
            )

        profile["age"] = random.randint(
            14,
            max_age,
        )

    # -------------------------------------------------------------
    # Gender
    # -------------------------------------------------------------

    if "gender" in rules:
        profile["gender"] = rules["gender"]

    # -------------------------------------------------------------
    # Residence
    # -------------------------------------------------------------

    if "residence" in rules:
        profile["residence"] = rules["residence"]

    # -------------------------------------------------------------
    # Occupation
    # -------------------------------------------------------------

    if "occupation_in" in rules:

        occupations = [
            occupation
            for occupation in rules["occupation_in"]
            if occupation in OCCUPATIONS
        ]

        if not occupations:
            raise ValueError(
                "No supported occupation found for rule: "
                f"{rules['occupation_in']}"
            )

        occupation = random.choice(occupations)

        profile["occupation"] = occupation

        profile["artisan_trade"] = None
        profile["street_vendor"] = False

        if occupation == "artisan":
            profile["artisan_trade"] = random.choice(
                ARTISAN_TRADES
            )

        if occupation == "street_vendor":
            profile["street_vendor"] = True

    # -------------------------------------------------------------
    # Income
    # -------------------------------------------------------------

    if "max_income" in rules:

        max_income = int(rules["max_income"])

        valid = [
            value
            for value in INCOMES
            if value <= max_income
        ]

        if valid:
            profile["annual_income"] = random.choice(valid)
        else:
            profile["annual_income"] = max_income

    if "min_income" in rules:

        min_income = int(rules["min_income"])

        valid = [
            value
            for value in INCOMES
            if value >= min_income
        ]

        if valid:
            profile["annual_income"] = random.choice(valid)
        else:
            profile["annual_income"] = min_income

    # -------------------------------------------------------------
    # Category
    # -------------------------------------------------------------

    if "category_in" in rules:
        categories = rules["category_in"]

        # Scheme data uses values such as "SC"/"ST"/"OBC",
        # while the synthetic profile vocabulary uses lowercase.
        normalized_categories = {
        str(category).strip().lower()
        for category in categories
        }

        valid = [
        category
        for category in CATEGORIES
        if category.lower() in normalized_categories
        ]

        if not valid:
            raise ValueError(
                f"No supported category found for rule: {categories}"
            )

        profile["category"] = random.choice(valid)

    # -------------------------------------------------------------
    # Religion
    # -------------------------------------------------------------

    if "religion_in" in rules:

        expected = rules["religion_in"]

        compatible = [
            value
            for value in expected
            if value in RELIGIONS
        ]

        if not compatible:
            # Handle lowercase dataset values if encountered.
            lower_map = {
                value.lower(): value
                for value in RELIGIONS
            }

            compatible = [
                lower_map[value.lower()]
                for value in expected
                if value.lower() in lower_map
            ]

        if not compatible:
            raise ValueError(
                "No supported religion found for rule: "
                f"{expected}"
            )

        profile["religion"] = random.choice(
            compatible
        )

    # -------------------------------------------------------------
    # Education
    # -------------------------------------------------------------

    if "education_in" in rules:

        expected = rules["education_in"]

        compatible = [
            value
            for value in expected
            if value in EDUCATION_LEVELS
        ]

        if not compatible:
            raise ValueError(
                "No supported education level found for rule: "
                f"{expected}"
            )

        profile["education_level"] = random.choice(
            compatible
        )

        # Keep class_level broadly consistent.
        education = profile["education_level"]

        if education == "below_10th":
            profile["class_level"] = random.choice(
                ["5", "6", "7", "8", "9"]
            )

        elif education == "10th_pass":
            profile["class_level"] = "10"

        elif education == "12th_pass":
            profile["class_level"] = "12"

        elif education == "ug":
            profile["class_level"] = "college"

        elif education == "pg":
            profile["class_level"] = "postgraduate"

        elif education == "not_studying":
            profile["class_level"] = "not_studying"

    # -------------------------------------------------------------
    # Disability
    # -------------------------------------------------------------

    if "min_disability_pct" in rules:

        minimum = int(
            rules["min_disability_pct"]
        )

        profile["disability_pct"] = max(
            minimum,
            random.choice(
                [
                    minimum,
                    minimum + 5,
                    minimum + 10,
                    minimum + 20,
                ]
            ),
        )

    # -------------------------------------------------------------
    # Marital status
    # -------------------------------------------------------------

    if "marital_status_in" in rules:

        expected = rules["marital_status_in"]

        compatible = [
            value
            for value in expected
            if value in MARITAL_STATUSES
        ]

        if not compatible:
            raise ValueError(
                "No supported marital status found for rule: "
                f"{expected}"
            )

        profile["marital_status"] = random.choice(
            compatible
        )

    # -------------------------------------------------------------
    # BPL
    # -------------------------------------------------------------

    if rules.get("requires_bpl_card") is True:
        profile["has_bpl_card"] = True

    # -------------------------------------------------------------
    # Cultivable land
    # -------------------------------------------------------------

    if rules.get("requires_cultivable_land") is True:
        profile["owns_cultivable_land"] = True

    # -------------------------------------------------------------
    # No pucca house
    # -------------------------------------------------------------

    if rules.get("requires_no_pucca_house") is True:
        profile["owns_pucca_house"] = False

    # -------------------------------------------------------------
    # Girl child under 10
    # -------------------------------------------------------------

    if rules.get("requires_girl_child_under_10") is True:
        profile["has_girl_child_under_10"] = True

    # -------------------------------------------------------------
    # Bank account
    # -------------------------------------------------------------

    if rules.get("requires_bank_account") is True:
        profile["has_bank_account"] = True

    # -------------------------------------------------------------
    # No LPG connection
    # -------------------------------------------------------------

    if rules.get("requires_no_lpg_connection") is True:
        profile["has_lpg_connection"] = False

    # -------------------------------------------------------------
    # No income tax
    # -------------------------------------------------------------

    if rules.get("requires_no_income_tax") is True:
        profile["income_tax_payer"] = False

    # -------------------------------------------------------------
    # Not government employee
    # -------------------------------------------------------------

    if rules.get("requires_not_government_employee") is True:
        profile["government_employee"] = False

    # -------------------------------------------------------------
    # Breadwinner death
    # -------------------------------------------------------------

    if rules.get("requires_breadwinner_death") is True:
        profile["breadwinner_deceased"] = True

    # -------------------------------------------------------------
    # Breadwinner age
    # -------------------------------------------------------------

    min_bw_age = rules.get("min_breadwinner_age")
    max_bw_age = rules.get("max_breadwinner_age")

    if min_bw_age is not None and max_bw_age is not None:

        min_bw_age = int(min_bw_age)
        max_bw_age = int(max_bw_age)

        if min_bw_age > max_bw_age:
            raise ValueError(
                "Impossible breadwinner age range: "
                f"{min_bw_age}>{max_bw_age}"
            )

        profile["breadwinner_age"] = random.randint(
            min_bw_age,
            max_bw_age,
        )

    elif min_bw_age is not None:

        min_bw_age = int(min_bw_age)

        profile["breadwinner_age"] = random.randint(
            min_bw_age,
            max(70, min_bw_age),
        )

    elif max_bw_age is not None:

        max_bw_age = int(max_bw_age)

        profile["breadwinner_age"] = random.randint(
            18,
            max_bw_age,
        )

    # -------------------------------------------------------------
    # Re-establish age-dependent coherence.
    # -------------------------------------------------------------

    age = profile["age"]

    if profile["occupation"] == "student":

        if age > 30:
            profile["age"] = random.randint(
                15,
                25,
            )

            age = profile["age"]

        profile["government_employee"] = False

    # Only update education automatically if the scheme does not
    # explicitly constrain education.
    if "education_in" not in rules:

        education, class_level = choose_education(
            age
        )

        profile["education_level"] = education
        profile["class_level"] = class_level

    return profile


# ---------------------------------------------------------------------
# Candidate validation
# ---------------------------------------------------------------------

def is_synthetic_eligible(profile, scheme):
    rules = get_synthetic_rules(scheme["rules"])

    # No profile-observable rules remain after removing
    # external verification. Therefore this scheme cannot
    # be used as a synthetic positive label.
    if rules is None:
        return False

    user_profile = UserProfile(**profile)

    status, _, unknowns = evaluate(
        user_profile,
        rules,
    )

    return status == "eligible"


def find_target_profile(
    target_scheme,
    schemes,
    attempts=50,
):
    """
    Construct multiple candidates for one target scheme.

    Every candidate is first modified using the target's rules.

    We then choose the candidate with the fewest other synthetic
    labels so the dataset does not become dominated by broad schemes
    such as PMSBY/PMJJBY/APY.

    The target itself must always be present.
    """

    target_id = target_scheme["id"]

    best_profile = None
    best_labels = None
    best_score = None

    for _ in range(attempts):

        profile = build_profile()

        try:
            profile = apply_rule_hints(
                profile,
                target_scheme["rules"],
            )
        except ValueError:
            # This indicates that the scheme contains a rule/value
            # combination unsupported by this synthetic profile
            # generator.
            continue

        # Direct validation of the target.
        if not is_synthetic_eligible(
            profile,
            target_scheme,
        ):
            continue

        labels = get_labels(
            profile,
            schemes,
        )

        if target_id not in labels:
            continue

        unwanted_labels = [
            label
            for label in labels
            if label != target_id
        ]

        score = len(unwanted_labels)

        if (
            best_score is None
            or score < best_score
        ):
            best_profile = profile
            best_labels = labels
            best_score = score

            # We cannot get better than an isolated example.
            if score == 0:
                break

    return (
        best_profile,
        best_labels,
    )


# ---------------------------------------------------------------------
# Profile -> natural language
# ---------------------------------------------------------------------

def profile_to_text(profile):
    """
    Ask the LLM to rewrite the structured profile into one concise
    natural-language sentence.

    The LLM does NOT determine eligibility.
    """

    prompt = f"""
Rewrite the following structured citizen profile into ONE concise,
natural-language sentence.

Rules:
- Do not determine scheme eligibility.
- Do not recommend any government scheme.
- Do not add facts.
- Do not remove important facts.
- Preserve all important eligibility-related facts.
- Clearly state both positive and negative facts when present.
- Return only the sentence.
- Make the sentence grammatically complete.
- End with a period, exclamation mark, or question mark.

Structured profile:
{json.dumps(profile, ensure_ascii=False)}
""".strip()

    try:

        result = _chat(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=400,
        )

        if isinstance(result, str):
            text = result.strip()

        elif isinstance(result, dict):
            text = (
                result.get("content")
                or result.get("text")
                or ""
            ).strip()

        else:
            text = str(result).strip()

        # Protect the dataset from truncated LLM outputs.
        if not text:
            return ""

        if text[-1] not in ".!?":
            print(
                "  LLM output appears truncated; "
                "using deterministic fallback text."
            )
            return ""

        return text

    except Exception as exc:

        print(
            f"  LLM generation failed: {exc}"
        )

        return ""


# ---------------------------------------------------------------------
# Deterministic fallback text
# ---------------------------------------------------------------------

def fallback_profile_text(profile):
    """
    Deterministic natural-language representation.

    This is used when the LLM fails or produces incomplete output.
    """

    parts = [
        f"{profile['age']} years old",
        profile["gender"],
        f"from {profile['state']}",
        f"living in a {profile['residence']} area",
        f"working as a {profile['occupation']}",
        f"with an annual income of ₹{profile['annual_income']}",
        f"with {profile['education_level']} education",
    ]

    if profile["category"]:
        parts.append(
            f"in the {profile['category']} category"
        )

    if profile["religion"]:
        parts.append(
            f"and follows {profile['religion']} religion"
        )

    if profile["has_bank_account"]:
        parts.append(
            "has a bank account"
        )
    else:
        parts.append(
            "does not have a bank account"
        )

    if profile["has_lpg_connection"]:
        parts.append(
            "has an LPG connection"
        )
    else:
        parts.append(
            "does not have an LPG connection"
        )

    if profile["income_tax_payer"]:
        parts.append(
            "is an income-tax payer"
        )
    else:
        parts.append(
            "is not an income-tax payer"
        )

    if profile["government_employee"]:
        parts.append(
            "is a government employee"
        )
    else:
        parts.append(
            "is not a government employee"
        )

    if profile["has_bpl_card"]:
        parts.append(
            "has a BPL or priority ration card"
        )
    else:
        parts.append(
            "does not have a BPL or priority ration card"
        )

    if profile["owns_cultivable_land"]:
        parts.append(
            "owns cultivable land"
        )
    else:
        parts.append(
            "does not own cultivable land"
        )

    if profile["owns_pucca_house"]:
        parts.append(
            "owns a pucca house"
        )
    else:
        parts.append(
            "does not own a pucca house"
        )

    if profile["has_girl_child_under_10"]:
        parts.append(
            "has a girl child under 10 years"
        )
    else:
        parts.append(
            "does not have a girl child under 10 years"
        )

    if profile["breadwinner_deceased"]:
        parts.append(
            "the primary breadwinner has died"
        )
    else:
        parts.append(
            "the primary breadwinner is living"
        )

    if profile["breadwinner_age"] is not None:
        parts.append(
            f"the primary breadwinner was "
            f"{profile['breadwinner_age']} years old"
        )

    if profile["disability_pct"]:
        parts.append(
            f"has {profile['disability_pct']}% disability"
        )
    else:
        parts.append(
            "has no recorded disability"
        )

    if profile["occupation"] == "artisan":
        parts.append(
            f"with artisan trade "
            f"{profile['artisan_trade']}"
        )

    if profile["street_vendor"]:
        parts.append(
            "and is a street vendor"
        )

    if profile["has_girl_child_under_10"]:
        parts.append(
            "and has a girl child below 10 years"
        )

    return ", ".join(parts) + "."


# ---------------------------------------------------------------------
# Main dataset generation
# ---------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate a balanced synthetic multi-label "
            "dataset for classifier-vs-LLM evaluation."
        )
    )

    parser.add_argument(
        "--target-per-scheme",
        type=int,
        default=20,
        help=(
            "Number of targeted profiles for EACH scheme. "
            "Default: 20."
        ),
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help=(
            "Delay between LLM requests in seconds. "
            "Default: 1."
        ),
    )

    parser.add_argument(
        "--target-attempts",
        type=int,
        default=50,
        help=(
            "Candidate construction attempts per targeted "
            "profile. Default: 50."
        ),
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help=(
            "Skip LLM paraphrasing and use deterministic "
            "fallback text."
        ),
    )

    args = parser.parse_args()

    if args.target_per_scheme <= 0:
        raise ValueError(
            "--target-per-scheme must be greater than 0."
        )

    if args.target_attempts <= 0:
        raise ValueError(
            "--target-attempts must be greater than 0."
        )

    random.seed(42)

    print()
    print("=" * 70)
    print("SYNTHETIC CLASSIFIER DATASET GENERATOR")
    print("=" * 70)

    # -------------------------------------------------------------
    # Load schemes.
    # -------------------------------------------------------------

    print()
    print("Loading schemes...")

    schemes = load_schemes()

    scheme_by_id = {
        scheme["id"]: scheme
        for scheme in schemes
    }

    print(
        f"Loaded {len(schemes)} schemes."
    )

    # -------------------------------------------------------------
    # Validate scheme inventory.
    # -------------------------------------------------------------

    missing_scheme_ids = [
        scheme_id
        for scheme_id in SCHEME_ORDER
        if scheme_id not in scheme_by_id
    ]

    unexpected_scheme_ids = [
        scheme_id
        for scheme_id in scheme_by_id
        if scheme_id not in SCHEME_ORDER
    ]

    if missing_scheme_ids:
        raise RuntimeError(
            "The database is missing expected schemes:\n"
            + "\n".join(
                f"  - {scheme_id}"
                for scheme_id in missing_scheme_ids
            )
        )

    if unexpected_scheme_ids:
        print(
            "WARNING: Database contains additional schemes "
            "not present in SCHEME_ORDER:"
        )

        for scheme_id in unexpected_scheme_ids:
            print(
                f"  - {scheme_id}"
            )

    if len(scheme_by_id) != 30:
        raise RuntimeError(
            "Expected exactly 30 schemes in the database, "
            f"but found {len(scheme_by_id)}."
        )

    print(
        "Verified: exactly 30 schemes."
    )

    # -------------------------------------------------------------
    # Identify schemes that can be labeled synthetically.
    # -------------------------------------------------------------

    synthetic_schemes = [
        scheme
        for scheme in schemes
        if get_synthetic_rules(scheme["rules"]) is not None
    ]

    unlabelable_schemes = [
        scheme
        for scheme in schemes
        if get_synthetic_rules(scheme["rules"]) is None
    ]

    print()
    print(
        f"Synthetically labelable schemes: "
        f"{len(synthetic_schemes)}"
    )

    print(
        f"Excluded from classifier targets: "
        f"{len(unlabelable_schemes)}"
    )

    if unlabelable_schemes:
        print(
            "Excluded schemes:"
        )

        for scheme in unlabelable_schemes:
            print(
                f"  - {scheme['id']}"
            )

    # -------------------------------------------------------------
    # Target plan.
    # -------------------------------------------------------------

    total_targeted = (
        len(synthetic_schemes)
        * args.target_per_scheme
    )

    print()
    print("Target distribution:")

    print(
        f"  Schemes:              "
        f"{len(synthetic_schemes)}"
    )

    print(
        f"  Profiles/scheme:      "
        f"{args.target_per_scheme}"
    )

    print(
        f"  Total targeted:       "
        f"{total_targeted}"
    )

    print(
        "  Random profiles:      0"
    )

    print()

    print("External verification:")

    print(
        "  Ignored ONLY for synthetic classifier labels."
    )

    print(
        "  Production rules.py remains unchanged."
    )

    # -------------------------------------------------------------
    # Generate targeted profiles.
    # -------------------------------------------------------------

    examples = []

    target_counts = {
        scheme["id"]: 0
        for scheme in synthetic_schemes
    }

    failed_targets = []

    for scheme_index, target_scheme in enumerate(
        synthetic_schemes,
        start=1,
    ):

        scheme_id = target_scheme["id"]

        print()
        print("=" * 70)

        print(
            f"[SCHEME {scheme_index}/{len(synthetic_schemes)}] "
            f"{scheme_id}"
        )

        print("=" * 70)

        generated_for_scheme = 0

        while (
            generated_for_scheme
            < args.target_per_scheme
        ):

            next_number = (
                generated_for_scheme + 1
            )

            print(
                f"[TARGET] "
                f"{scheme_id} "
                f"{next_number}/"
                f"{args.target_per_scheme}"
            )

            profile, labels = find_target_profile(
                target_scheme,
                schemes,
                attempts=args.target_attempts,
            )

            # -----------------------------------------------------
            # Candidate construction failed.
            # -----------------------------------------------------

            if profile is None:

                print(
                    f"  FAILED: could not construct "
                    f"a synthetic-positive profile."
                )

                failed_targets.append(
                    scheme_id
                )

                break

            # -----------------------------------------------------
            # Final deterministic validation.
            # -----------------------------------------------------

            if not is_synthetic_eligible(
                profile,
                target_scheme,
            ):

                raise RuntimeError(
                    "INTERNAL ERROR: target profile failed "
                    "final validation for "
                    f"{scheme_id}"
                )

            if scheme_id not in labels:

                raise RuntimeError(
                    "INTERNAL ERROR: target scheme "
                    f"{scheme_id} missing from labels."
                )

            print(
                f"  Labels: {labels}"
            )

            # -----------------------------------------------------
            # Natural language generation.
            # -----------------------------------------------------

            if args.no_llm:

                text = fallback_profile_text(
                    profile
                )

            else:

                text = profile_to_text(
                    profile
                )

            # -----------------------------------------------------
            # Fallback if LLM generation fails.
            # -----------------------------------------------------

            if not text:

                text = fallback_profile_text(
                    profile
                )

                print(
                    "  Using deterministic fallback text."
                )

            # -----------------------------------------------------
            # Store generated example.
            # -----------------------------------------------------

            examples.append(
                {
                    "text": text,
                    "profile": profile,
                    "labels": labels,
                    "target_scheme": scheme_id,
                    "source": "targeted",
                }
            )

            # -----------------------------------------------------
            # IMPORTANT:
            # Increment ONLY after successful example creation.
            # -----------------------------------------------------

            generated_for_scheme += 1

            target_counts[scheme_id] = (
                generated_for_scheme
            )

            print(
                f"  Generated: "
                f"{generated_for_scheme}/"
                f"{args.target_per_scheme}"
            )

            if args.sleep > 0:
                time.sleep(
                    args.sleep
                )

        # ---------------------------------------------------------
        # Fail immediately if the scheme did not reach its target.
        # ---------------------------------------------------------

        if (
            generated_for_scheme
            != args.target_per_scheme
        ):

            raise RuntimeError(
                "\n"
                f"Could not generate exactly "
                f"{args.target_per_scheme} "
                f"profiles for {scheme_id}.\n"
                f"Generated: {generated_for_scheme}\n"
                "\n"
                "The generator will NOT save a partial dataset.\n"
                "\n"
                "This usually means one of the following:\n"
                "1. The scheme contains a rule that the synthetic "
                "profile generator does not support.\n"
                "2. The scheme rules are internally inconsistent.\n"
                "3. The current UserProfile/rules vocabulary does "
                "not match the scheme data.\n"
            )

    # -------------------------------------------------------------
    # Final target count.
    # -------------------------------------------------------------

    expected_total = (
        len(synthetic_schemes)
        * args.target_per_scheme
    )

    if len(examples) != expected_total:

        raise RuntimeError(
            "Final dataset size mismatch.\n"
            f"Expected: {expected_total}\n"
            f"Generated: {len(examples)}"
        )

    # -------------------------------------------------------------
    # Final per-scheme count validation.
    # -------------------------------------------------------------

    final_target_counts = {
        scheme["id"]: 0
        for scheme in synthetic_schemes
    }

    for example in examples:

        target = example[
            "target_scheme"
        ]

        if target not in final_target_counts:

            raise RuntimeError(
                "Unknown target scheme in generated "
                f"dataset: {target}"
            )

        final_target_counts[target] += 1

    incorrect_distribution = {
        scheme_id: count
        for scheme_id, count
        in final_target_counts.items()
        if count != args.target_per_scheme
    }

    if incorrect_distribution:

        raise RuntimeError(
            "Target distribution is incorrect:\n"
            + "\n".join(
                f"  {scheme_id}: {count}"
                for scheme_id, count
                in incorrect_distribution.items()
            )
        )

    # -------------------------------------------------------------
    # Check text and labels.
    # -------------------------------------------------------------

    empty_text = 0
    empty_labels = 0
    total_labels = 0
    multi_label_count = 0

    positive_counts = {
        scheme_id: 0
        for scheme_id in SCHEME_ORDER
    }

    for example in examples:

        text = example["text"]
        labels = example["labels"]

        if not text:
            empty_text += 1

        if not labels:
            empty_labels += 1

        total_labels += len(labels)

        if len(labels) > 1:
            multi_label_count += 1

        for label in labels:

            if label not in positive_counts:

                raise RuntimeError(
                    "Unknown label generated: "
                    f"{label}"
                )

            positive_counts[label] += 1

    if empty_text:

        raise RuntimeError(
            f"Dataset contains {empty_text} empty text examples."
        )

    if empty_labels:

        raise RuntimeError(
            f"Dataset contains {empty_labels} empty-label examples."
        )

    # -------------------------------------------------------------
    # Save dataset.
    # -------------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        for example in examples:

            f.write(
                json.dumps(
                    example,
                    ensure_ascii=False,
                )
                + "\n"
            )

    # -------------------------------------------------------------
    # Summary.
    # -------------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("DATASET GENERATION COMPLETE")
    print("=" * 70)

    print(
        f"Requested targeted profiles: "
        f"{expected_total}"
    )

    print(
        f"Generated profiles:           "
        f"{len(examples)}"
    )

    print(
        f"Targeted profiles:             "
        f"{len(examples)}"
    )

    print(
        "Random profiles:               0"
    )

    print(
        f"Targetable schemes:            "
        f"{len(synthetic_schemes)}"
    )

    print(
        f"Excluded schemes:              "
        f"{len(unlabelable_schemes)}"
    )

    print(
        f"Zero-label examples:           "
        f"{empty_labels}"
    )

    print(
        f"Multi-label examples:          "
        f"{multi_label_count}"
    )

    print(
        f"Average labels/profile:        "
        f"{total_labels / len(examples):.2f}"
    )

    print()
    print("Target distribution:")
    print("-" * 50)

    for scheme_id in SCHEME_ORDER:

        if scheme_id in final_target_counts:

            print(
                f"{scheme_id:<28} "
                f"{final_target_counts[scheme_id]}"
            )

        else:

            print(
                f"{scheme_id:<28} "
                f"EXCLUDED"
            )

    print()
    print("Total positive label counts:")
    print("-" * 50)

    for scheme_id in SCHEME_ORDER:

        print(
            f"{scheme_id:<28} "
            f"{positive_counts[scheme_id]}"
        )

    print()
    print(
        f"Saved to: {OUTPUT_PATH}"
    )

    print()
    print(
        "VALIDATION: PASS"
    )

    print(
        f"{len(synthetic_schemes)} targetable schemes × "
        f"{args.target_per_scheme} targeted profiles "
        f"= {expected_total} profiles."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()