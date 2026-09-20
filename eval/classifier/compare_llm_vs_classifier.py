from functools import cache
import os
import sys
import json
import time
import pickle
import random
import statistics
import re
from pathlib import Path
from urllib import response

import numpy as np
from dotenv import load_dotenv

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    hamming_loss,
)


# ---------------------------------------------------------------------
# PATH SETUP
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from backend.llm import _chat


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

DATASET_PATH = (
    ROOT
    / "eval"
    / "classifier"
    / "synthetic_dataset.jsonl"
)

MODEL_PATH = (
    ROOT
    / "eval"
    / "classifier"
    / "model.pkl"
)

CACHE_PATH = (
    ROOT
    / "eval"
    / "classifier"
    / "llm_cache.json"
)

TEST_INDICES_PATH = (
    ROOT
    / "eval"
    / "classifier"
    / "test_indices.json"
)

REPORT_PATH = (
    ROOT
    / "eval"
    / "classifier"
    / "comparison_report.json"
)


# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

SEED = 42
DEFAULT_SAMPLE = 10
LLM_REQUEST_INTERVAL_SECONDS = 8.0

random.seed(SEED)
np.random.seed(SEED)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def normalize_ids(ids):
    """
    Normalize scheme IDs into a sorted list of strings.
    """

    if ids is None:
        return []

    if isinstance(ids, str):
        ids = [ids]

    if not isinstance(ids, (list, tuple, set)):
        return []

    return sorted(
        str(x).strip()
        for x in ids
        if str(x).strip()
    )


def load_dataset():
    rows = []

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            rows.append(json.loads(line))

    return rows


def load_classifier():
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)

    required_keys = [
        "vectorizer",
        "classifier",
        "mlb",
    ]

    missing = [
        key
        for key in required_keys
        if key not in bundle
    ]

    if missing:
        raise ValueError(
            f"Classifier bundle missing keys: {missing}"
        )

    print(
        "Classifier bundle keys:",
        list(bundle.keys()),
    )

    print(
        "Classifier model loaded :",
        MODEL_PATH,
    )

    return bundle


def load_test_indices():
    """
    Load persisted test indices.

    Supports both:

    1. Raw list:
       [1, 5, 10, 20]

    2. Metadata object:
       {
           "dataset_size": 520,
           "test_size": 130,
           "indices": [...]
       }
    """

    if not TEST_INDICES_PATH.exists():
        raise FileNotFoundError(
            f"Missing test indices file: {TEST_INDICES_PATH}"
        )

    with open(
        TEST_INDICES_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    # -------------------------------------------------------------
    # Case 1: raw list
    # -------------------------------------------------------------

    if isinstance(data, list):
        return [
            int(i)
            for i in data
        ]

    # -------------------------------------------------------------
    # Case 2: metadata dictionary
    # -------------------------------------------------------------

    if isinstance(data, dict):

        for key in [
            "indices",
            "test_indices",
            "test_index",
        ]:

            if key in data:

                indices = data[key]

                if isinstance(indices, list):
                    return [
                        int(i)
                        for i in indices
                    ]

        raise ValueError(
            "test_indices.json is a dictionary, "
            "but no test-index list was found. "
            f"Available keys: {list(data.keys())}"
        )

    raise ValueError(
        "Unsupported test_indices.json format: "
        f"{type(data).__name__}"
    )


def load_cache():

    if not CACHE_PATH.exists():
        return {}

    try:

        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as f:

            cache = json.load(f)

        if not isinstance(cache, dict):
            return {}

        return cache

    except Exception:

        print(
            "[CACHE] Invalid cache file. Starting empty."
        )

        return {}


def save_cache(cache):

    with open(
        CACHE_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            cache,
            f,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------
# CLASSIFIER
# ---------------------------------------------------------------------

def classifier_predict(bundle, text):
    """
    Predict scheme IDs using the trained
    TF-IDF + One-vs-Rest classifier.
    """

    start = time.perf_counter()

    vectorizer = bundle["vectorizer"]
    classifier = bundle["classifier"]
    mlb = bundle["mlb"]

    X = vectorizer.transform([text])

    prediction = classifier.predict(X)

    predicted_ids = mlb.inverse_transform(
        prediction
    )[0]

    predicted_ids = normalize_ids(
        predicted_ids
    )

    latency = time.perf_counter() - start

    return predicted_ids, latency


# ---------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------

def build_llm_messages(text):
    system_prompt = """
Extract structured facts from the user profile.

Return ONLY valid JSON.
Use only facts explicitly stated or strongly implied.
Do not invent or infer unsupported facts.
Omit unknown fields.
Do not determine eligibility.
Do not return scheme IDs.

Fields:
age, gender, state, residence, annual_income, category, religion,
occupation, education_level, marital_status, disability_pct,
has_bpl_card, owns_cultivable_land, owns_pucca_house,
has_girl_child_under_10, has_bank_account, has_lpg_connection,
income_tax_payer, government_employee, breadwinner_deceased,
breadwinner_age, class_level, academic_percentage,
receives_other_scholarship, artisan_trade, street_vendor,
existing_business, documents_have, extra_info
"""

    return [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
        {
            "role": "user",
            "content": text,
        },
    ]


def parse_llm_json(content):
    """
    Parse JSON returned by the LLM.

    Handles occasional markdown fences.
    """

    if not isinstance(content, str):
        raise ValueError(
            "Expected string response, "
            f"got {type(content).__name__}"
        )

    content = content.strip()

    if not content:
        raise ValueError(
            "Empty LLM response"
        )

    # Remove markdown code fences.
    if content.startswith("```"):

        lines = content.splitlines()

        if (
            lines
            and lines[0].startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        content = "\n".join(
            lines
        ).strip()

    try:

        data = json.loads(content)

    except json.JSONDecodeError as e:

        raise ValueError(
            f"Invalid JSON from LLM: {e}"
        )

    if not isinstance(data, dict):
        raise ValueError(
            "LLM JSON response must be an object"
        )

    return data


# ---------------------------------------------------------------------
# PROFILE -> USER PROFILE -> RULE ENGINE
# ---------------------------------------------------------------------

def convert_to_user_profile(profile_data):
    """
    Convert the extracted dictionary into the project's UserProfile.

    We import UserProfile dynamically so this evaluation script does
    not modify the production implementation.
    """

    from backend.models import UserProfile

    allowed_fields = set(
        getattr(
            UserProfile,
            "model_fields",
            {},
        ).keys()
    )

    clean_profile = {
        key: value
        for key, value in profile_data.items()
        if key in allowed_fields
    }

    return UserProfile(
        **clean_profile
    )


def evaluate_profile(profile_data):
    """
    Convert LLM-extracted facts into UserProfile and evaluate the
    profile using the SAME synthetic rules used to generate the
    classifier labels.

    This function is ONLY for the LLM-vs-classifier experiment.

    Production eligibility is unchanged:

        EligibilityAgent -> production rules

    The synthetic rules remove only:

        requires_external_verification

    because that condition cannot be inferred from the generated
    profile.
    """

    from backend.models import UserProfile
    from backend.rules import evaluate
    from backend.database import db_connection
    from eval.classifier.generate_synthetic_profiles import (
        get_synthetic_rules,
    )

    allowed_fields = set(
        UserProfile.model_fields.keys()
    )

    clean_profile = {
        key: value
        for key, value in profile_data.items()
        if key in allowed_fields
    }

    profile = UserProfile(
        **clean_profile
    )

    print()
    print("[LLM] Extracted profile:")
    print(
        json.dumps(
            clean_profile,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    eligible_ids = []

    with (
        db_connection() as conn,
        conn.cursor() as cur
    ):

        cur.execute(
            "SELECT id, data FROM schemes ORDER BY id"
        )

        rows = cur.fetchall()

    for row in rows:

        scheme_id = str(row["id"])

        scheme = row["data"]

        production_rules = (
            scheme.get("rules") or {}
        )

        # EXACT same transformation used by
        # generate_synthetic_profiles.py
        synthetic_rules = get_synthetic_rules(
            production_rules
        )

        # No profile-observable rules remain.
        if synthetic_rules is None:
            continue

        status, reasons, unknowns = evaluate(
            profile,
            synthetic_rules,
        )

        if status == "eligible":

            eligible_ids.append(
                scheme_id
            )

        elif status == "ineligible":

            print(
                f"[RULE] {scheme_id}: INELIGIBLE"
            )

            if reasons:
                print(
                    f"       reasons: {reasons}"
                )

        elif status == "possible":

            print(
                f"[RULE] {scheme_id}: POSSIBLE"
            )

            if unknowns:
                print(
                    f"       unknown: {unknowns}"
                )

    return sorted(
        set(eligible_ids)
    )


# ---------------------------------------------------------------------
# LLM PROFILE EXTRACTION
# ---------------------------------------------------------------------

def llm_extract_profile(text):
    """
    Extract a structured profile from free text using the project's
    existing _chat() function.

    Rate-limit errors are retried using the provider-suggested delay
    when available, otherwise exponential backoff is used.

    This function does NOT determine eligibility.
    """

    messages = build_llm_messages(text)

    max_retries = 5

    base_delay = 2.0

    max_delay = 20.0

    total_start = time.perf_counter()

    for attempt in range(
        max_retries + 1
    ):

        start = time.perf_counter()

        try:

            print(
                "[LLM] Calling model:",
                os.getenv(
                    "LLM_MODEL",
                    "configured model",
                ),
                f"(attempt {attempt + 1}/"
                f"{max_retries + 1})",
            )

            content = _chat(
                messages,
                max_tokens=500,
            )

            latency = (
                time.perf_counter()
                - start
            )

            if content is None:

                return {
                    "success": False,
                    "api_failed": True,
                    "rate_limit": False,
                    "validation_failed": False,
                    "profile": None,
                    "latency_seconds": (
                        time.perf_counter()
                        - total_start
                    ),
                    "error": (
                        "LLM returned None"
                    ),
                }

            # ---------------------------------------------------------
            # Parse JSON
            # ---------------------------------------------------------

            try:

                profile = parse_llm_json(
                    content
                )

            except Exception as e:

                return {
                    "success": False,
                    "api_failed": False,
                    "rate_limit": False,
                    "validation_failed": True,
                    "profile": None,
                    "latency_seconds": (
                        time.perf_counter()
                        - total_start
                    ),
                    "error": str(e),
                }

            # ---------------------------------------------------------
            # Successful extraction
            # ---------------------------------------------------------

            return {
                "success": True,
                "api_failed": False,
                "rate_limit": False,
                "validation_failed": False,
                "profile": profile,
                "latency_seconds": (
                    time.perf_counter()
                    - total_start
                ),
                "error": None,
            }

        except Exception as e:

            error_text = str(e)

            # ---------------------------------------------------------
            # Detect rate limit
            # ---------------------------------------------------------

            is_rate_limit = (
                
                 "429" in error_text
                 or "rate_limit" in error_text.lower()
                 or "rate limit" in error_text.lower()
                 or "rate_limit_exceeded" in error_text.lower()
                 or "too many requests" in error_text.lower()
                 or "tokens per minute" in error_text.lower()
                 or "tpm" in error_text.lower()
            )

            # ---------------------------------------------------------
            # Non-rate-limit failure
            # ---------------------------------------------------------

            if not is_rate_limit:

                return {
                    "success": False,
                    "api_failed": True,
                    "rate_limit": False,
                    "validation_failed": False,
                    "profile": None,
                    "latency_seconds": (
                        time.perf_counter()
                        - total_start
                    ),
                    "error": error_text,
                }

            # ---------------------------------------------------------
            # Rate limit + retries exhausted
            # ---------------------------------------------------------

            if attempt >= max_retries:

                print(
                    "[LLM] Rate limit persisted "
                    f"after {max_retries + 1} attempts."
                )

                return {
                    "success": False,
                    "api_failed": False,
                    "rate_limit": True,
                    "validation_failed": False,
                    "profile": None,
                    "latency_seconds": (
                        time.perf_counter()
                        - total_start
                    ),
                    "error": error_text,
                }

            # ---------------------------------------------------------
            # Extract provider suggested delay
            #
            # Example:
            #
            # Please try again in 1.5525s
            # ---------------------------------------------------------

            delay_match = re.search(
                r"try again in\s+"
                r"([0-9]+(?:\.[0-9]+)?)\s*(ms|s)",
                error_text,
                re.IGNORECASE,
            )

            if delay_match:
                provider_delay = float(
                delay_match.group(1)
              )
                unit = delay_match.group(2).lower()
                if unit == "ms":
                    provider_delay /= 1000.0
                    
                delay = max(
                    provider_delay + 1.0,
                    3.0,
                )

            else:
                delay = min(
                    base_delay * (2 ** attempt),
                    max_delay,
                )

            print(
                "[LLM] Rate limit detected (429). "
                f"Retrying in {delay:.2f}s..."
            )

            time.sleep(delay)

    # Should never be reached.

    return {
        "success": False,
        "api_failed": False,
        "rate_limit": True,
        "validation_failed": False,
        "profile": None,
        "latency_seconds": (
            time.perf_counter()
            - total_start
        ),
        "error": (
            "Unexpected retry loop termination"
        ),
    }






# ---------------------------------------------------------------------
# LLM PREDICTION
# ---------------------------------------------------------------------

def llm_predict(
    text,
    cache,
    cache_key,
    use_cache=True,
):
    """
    Complete LLM evaluation pipeline.

    Flow:

        text
          ↓
        LLM profile extraction
          ↓
        UserProfile
          ↓
        deterministic rule evaluation
          ↓
        eligible scheme IDs

    The LLM itself never decides eligibility.

    Cached successful predictions are reused.
    Failed results are NOT cached so they can be retried
    on a future benchmark run.
    """

    # -------------------------------------------------------------
    # CACHE
    # -------------------------------------------------------------

    if use_cache and cache_key in cache:

        cached = cache[cache_key]

        # Only use a cache entry if it has the expected structure.
        if isinstance(cached, dict):

            eligible_ids = normalize_ids(
                cached.get(
                    "eligible_ids",
                    [],
                )
            )

            return {
                "success": True,
                "cache_hit": True,
                "eligible_ids": eligible_ids,
                "latency_seconds": cached.get(
                    "latency_seconds"
                ),
                "api_failed": False,
                "rate_limit": False,
                "validation_failed": False,
                "error": None,
            }

    # -------------------------------------------------------------
    # LLM EXTRACTION
    # -------------------------------------------------------------

    extraction_result = (
        llm_extract_profile(text)
    )

    if not extraction_result["success"]:

        return {
            "success": False,
            "cache_hit": False,
            "eligible_ids": [],
            "latency_seconds": (
                extraction_result.get(
                    "latency_seconds"
                )
            ),
            "api_failed": extraction_result.get(
                "api_failed",
                False,
            ),
            "rate_limit": extraction_result.get(
                "rate_limit",
                False,
            ),
            "validation_failed": (
                extraction_result.get(
                    "validation_failed",
                    False,
                )
            ),
            "error": extraction_result.get(
                "error"
            ),
        }

    # -------------------------------------------------------------
    # PROFILE -> RULE ENGINE
    # -------------------------------------------------------------

    try:

        eligible_ids = evaluate_profile(
            extraction_result["profile"]
        )

    except Exception as e:

        return {
            "success": False,
            "cache_hit": False,
            "eligible_ids": [],
            "latency_seconds": (
                extraction_result.get(
                    "latency_seconds"
                )
            ),
            "api_failed": False,
            "rate_limit": False,
            "validation_failed": True,
            "error": (
                "Rule evaluation failed: "
                f"{e}"
            ),
        }

    eligible_ids = normalize_ids(
        eligible_ids
    )

    latency_seconds = extraction_result.get(
        "latency_seconds"
    )

    # -------------------------------------------------------------
    # SAVE ONLY SUCCESSFUL RESULT
    # -------------------------------------------------------------

    cache[cache_key] = {
        "eligible_ids": eligible_ids,
        "latency_seconds": latency_seconds,
    }

    return {
        "success": True,
        "cache_hit": False,
        "eligible_ids": eligible_ids,
        "latency_seconds": latency_seconds,
        "api_failed": False,
        "rate_limit": False,
        "validation_failed": False,
        "error": None,
    }


# ---------------------------------------------------------------------
# METRICS
# ---------------------------------------------------------------------

def calculate_metrics(
    y_true,
    y_pred,
    mlb,
):
    """
    Calculate identical multilabel metrics
    for both systems.
    """

    if not y_true:
        return None

    y_true_matrix = mlb.transform(
        y_true
    )

    y_pred_matrix = mlb.transform(
        y_pred
    )

    return {
        "micro_precision": float(
            precision_score(
                y_true_matrix,
                y_pred_matrix,
                average="micro",
                zero_division=0,
            )
        ),

        "micro_recall": float(
            recall_score(
                y_true_matrix,
                y_pred_matrix,
                average="micro",
                zero_division=0,
            )
        ),

        "micro_f1": float(
            f1_score(
                y_true_matrix,
                y_pred_matrix,
                average="micro",
                zero_division=0,
            )
        ),

        "macro_precision": float(
            precision_score(
                y_true_matrix,
                y_pred_matrix,
                average="macro",
                zero_division=0,
            )
        ),

        "macro_recall": float(
            recall_score(
                y_true_matrix,
                y_pred_matrix,
                average="macro",
                zero_division=0,
            )
        ),

        "macro_f1": float(
            f1_score(
                y_true_matrix,
                y_pred_matrix,
                average="macro",
                zero_division=0,
            )
        ),

        "weighted_precision": float(
            precision_score(
                y_true_matrix,
                y_pred_matrix,
                average="weighted",
                zero_division=0,
            )
        ),

        "weighted_recall": float(
            recall_score(
                y_true_matrix,
                y_pred_matrix,
                average="weighted",
                zero_division=0,
            )
        ),

        "weighted_f1": float(
            f1_score(
                y_true_matrix,
                y_pred_matrix,
                average="weighted",
                zero_division=0,
            )
        ),

        "exact_match": float(
            accuracy_score(
                y_true_matrix,
                y_pred_matrix,
            )
        ),

        "hamming_loss": float(
            hamming_loss(
                y_true_matrix,
                y_pred_matrix,
            )
        ),
    }


def latency_stats(values):

    if not values:
        return None

    values = sorted(values)

    return {
        "count": len(values),

        "average_ms": (
            statistics.mean(values)
            * 1000
        ),

        "median_ms": (
            statistics.median(values)
            * 1000
        ),

        "p95_ms": (
            float(
                np.percentile(
                    values,
                    95,
                )
            )
            * 1000
        ),
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--sample",
        type=int,
        default=DEFAULT_SAMPLE,
        help=(
            "Number of test examples "
            "to evaluate"
        ),
    )

    parser.add_argument(
        "--uncached-only",
        action="store_true",
        help=(
            "Evaluate only test examples "
            "that do not have cached LLM predictions"
        ),
    )

    args = parser.parse_args()

    print("=" * 70)
    print("LLM vs CLASSIFIER COMPARISON")
    print("=" * 70)

    # -------------------------------------------------------------
    # Load dataset
    # -------------------------------------------------------------

    dataset = load_dataset()

    print(
        f"Total dataset examples : "
        f"{len(dataset)}"
    )

    # -------------------------------------------------------------
    # Load classifier
    # -------------------------------------------------------------

    bundle = load_classifier()

    mlb = bundle["mlb"]

    # -------------------------------------------------------------
    # Load test indices
    # -------------------------------------------------------------

    test_indices = load_test_indices()

    print(
        "Using persisted test indices: "
        f"{len(test_indices)} examples"
    )

    print(
        "Test examples available : "
        f"{len(test_indices)}"
    )

    # -------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------

    cache = load_cache()

    print(
        "Cached LLM predictions   : "
        f"{len(cache)}"
    )

    print("[CACHE DEBUG] Sample cache keys:")
    print(list(cache.keys())[:20])

    print("[CACHE DEBUG] Key types:")
    print(
        set(
            type(k).__name__
            for k in cache.keys()
        )
    )

    # -------------------------------------------------------------
    # Select examples
    # -------------------------------------------------------------

    if args.uncached_only:

        available_indices = [
            index
            for index in test_indices
            if str(index) not in cache
        ]

        print(
            "[CACHE DEBUG] Selected uncached candidates:"
        )
        print(
            available_indices[:20]
        )

        print(
            "[CACHE DEBUG] Check selected keys:"
        )

        for index in available_indices[:5]:

            print(
                index,
                "->",
                str(index),
                "in cache =",
                str(index) in cache,
            )

        print(
            "Uncached test examples  : "
            f"{len(available_indices)}"
        )

        sample_size = min(
            args.sample,
            len(available_indices),
        )

        # Deterministic selection
        selected_indices = (
            available_indices[:sample_size]
        )

    else:

        sample_size = min(
            args.sample,
            len(test_indices),
        )

        rng = random.Random(SEED)

        selected_indices = rng.sample(
            test_indices,
            sample_size,
        )

    # -------------------------------------------------------------
    # Final selection safety check
    # -------------------------------------------------------------

    print()
    print("=" * 70)
    print("[DEBUG] FINAL selected_indices")
    print(selected_indices)
    print("=" * 70)

    if args.uncached_only:

        cached_selected = [
            index
            for index in selected_indices
            if str(index) in cache
        ]

        if cached_selected:

            raise RuntimeError(
                "BUG: --uncached-only selected "
                "cached examples: "
                f"{cached_selected}"
            )

        for index in selected_indices:

            print(
                f"[DEBUG] {index} -> "
                f"in cache = "
                f"{str(index) in cache}"
            )
    # -------------------------------------------------------------
    # Handle empty uncached selection
    # -------------------------------------------------------------

    if not selected_indices:

        print()
        print("=" * 70)
        print("NO UNCACHED EXAMPLES AVAILABLE")
        print("=" * 70)

        if args.uncached_only:
            print(
                "All test examples already have cached "
                "LLM predictions."
            )
            print(
                "No LLM API calls were made."
            )
            print(
                "Run without --uncached-only to "
                "evaluate the cached test set."
            )
        else:
            print(
                "No examples were selected for evaluation."
            )

        print("=" * 70)

        return

    # -------------------------------------------------------------
    # Results
    # -------------------------------------------------------------

    y_true_classifier = []
    y_pred_classifier = []

    y_true_llm = []
    y_pred_llm = []

    classifier_latencies = []
    llm_latencies = []

    # -------------------------------------------------------------
    # Operational counters
    # -------------------------------------------------------------

    llm_attempted = 0
    llm_successful = 0
    llm_failed = 0
    llm_cache_hits = 0
    llm_api_failures = 0
    llm_rate_limits = 0
    llm_validation_failures = 0

    last_llm_request_time = None

    # -------------------------------------------------------------
    # Evaluate examples
    # -------------------------------------------------------------

    for counter, dataset_index in enumerate(
        selected_indices,
        start=1,
    ):

        row = dataset[dataset_index]

        text = row["text"]

        ground_truth = normalize_ids(
            row["labels"]
        )

        target_scheme = row.get(
            "target_scheme",
            "unknown",
        )

        print()
        print("-" * 70)

        print(
            f"Example "
            f"{counter}/{len(selected_indices)}"
        )

        print(
            f"Dataset index : {dataset_index}"
        )

        print(
            f"Target scheme : {target_scheme}"
        )

        print(
            "Ground truth  :",
            ", ".join(ground_truth),
        )

        # =========================================================
        # CLASSIFIER
        # =========================================================

        (
            classifier_prediction,
            classifier_latency,
        ) = classifier_predict(
            bundle,
            text,
        )

        classifier_latencies.append(
            classifier_latency
        )

        y_true_classifier.append(
            ground_truth
        )

        y_pred_classifier.append(
            classifier_prediction
        )

        print(
            "Classifier    :",
            ", ".join(
                classifier_prediction
            )
            if classifier_prediction
            else "(none)",
        )

        print(
            "Classifier latency : "
            f"{classifier_latency * 1000:.2f} ms"
        )

        # =========================================================
        # LLM
        # =========================================================

        llm_attempted += 1

        cache_key = str(
            dataset_index
        )

        # ---------------------------------------------------------
        # Pace fresh API calls to stay below Groq TPM limit.
        # Cached predictions do not consume API tokens.
        # ---------------------------------------------------------

        if cache_key not in cache:

            if last_llm_request_time is not None:

                elapsed = (
                    time.perf_counter()
                    - last_llm_request_time
                )

                remaining = (
                    LLM_REQUEST_INTERVAL_SECONDS
                    - elapsed
                )

                if remaining > 0:

                    print(
                        f"[LLM] Waiting "
                        f"{remaining:.2f}s "
                        "before next API request..."
                    )

                    time.sleep(
                        remaining
                    )

            last_llm_request_time = (
                time.perf_counter()
            )

        llm_result = llm_predict(
            text,
            cache,
            cache_key,
            use_cache=True,
        )

        if llm_result["cache_hit"]:

            llm_cache_hits += 1

        if llm_result["success"]:

            llm_successful += 1

            llm_prediction = normalize_ids(
                llm_result["eligible_ids"]
            )

            # -----------------------------------------------------
            # Only successful LLM evaluations
            # enter quality metrics.
            # -----------------------------------------------------

            y_true_llm.append(
                ground_truth
            )

            y_pred_llm.append(
                llm_prediction
            )

            # -----------------------------------------------------
            # Record latency only for fresh API calls.
            # -----------------------------------------------------

            if (
                not llm_result["cache_hit"]
                and
                llm_result["latency_seconds"]
                is not None
            ):

                llm_latencies.append(
                    llm_result[
                        "latency_seconds"
                    ]
                )

            if llm_result["cache_hit"]:

                print(
                    "LLM status    : [CACHE HIT]"
                )

            else:

                print(
                    "LLM status    : [SUCCESS]"
                )

            print(
                "LLM prediction:",
                ", ".join(
                    llm_prediction
                )
                if llm_prediction
                else "(none)",
            )

            # -----------------------------------------------------
            # Save newly generated prediction immediately.
            # -----------------------------------------------------

            if not llm_result["cache_hit"]:

                save_cache(cache)

        else:

            llm_failed += 1

            if llm_result["rate_limit"]:

                llm_rate_limits += 1

                print(
                    "LLM status    : "
                    "[RATE LIMITED]"
                )

            elif llm_result[
                "validation_failed"
            ]:

                llm_validation_failures += 1

                print(
                    "LLM status    : "
                    "[VALIDATION FAILED]"
                )

            else:

                llm_api_failures += 1

                print(
                    "LLM status    : "
                    "[API FAILED]"
                )

            print(
                "LLM prediction: [NOT SCORED]"
            )

    # -------------------------------------------------------------
    # Save cache
    # -------------------------------------------------------------

    save_cache(cache)

    # -------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------

    llm_metrics = calculate_metrics(
        y_true_llm,
        y_pred_llm,
        mlb,
    )

    classifier_metrics = calculate_metrics(
        y_true_classifier,
        y_pred_classifier,
        mlb,
    )

    # -------------------------------------------------------------
    # Operational statistics
    # -------------------------------------------------------------

    llm_success_rate = (
        llm_successful / llm_attempted
        if llm_attempted
        else 0
    )

    llm_failure_rate = (
        llm_failed / llm_attempted
        if llm_attempted
        else 0
    )

    llm_cache_hit_rate = (
        llm_cache_hits / llm_attempted
        if llm_attempted
        else 0
    )

    # -------------------------------------------------------------
    # Labels
    # -------------------------------------------------------------

    labels = sorted(
        str(x)
        for x in mlb.classes_
    )

    print(
        "Dataset labels           : "
        f"{len(labels)}"
    )

    print(
        "Labels:",
        ", ".join(labels),
    )

    # -------------------------------------------------------------
    # Report
    # -------------------------------------------------------------

    report = {

        "dataset": {

            "total_examples": len(
                dataset
            ),

            "test_examples": len(
                test_indices
            ),

            "evaluated_examples": len(
                selected_indices
            ),

            "number_of_labels": len(
                labels
            ),

            "labels": labels,

            "seed": SEED,
        },

        "llm_operational_statistics": {

            "examples_attempted":
                llm_attempted,

            "successful_evaluations":
                llm_successful,

            "failed_evaluations":
                llm_failed,

            "success_rate":
                llm_success_rate,

            "failure_rate":
                llm_failure_rate,

            "cache_hits":
                llm_cache_hits,

            "cache_hit_rate":
                llm_cache_hit_rate,

            "api_failures":
                llm_api_failures,

            "rate_limit_failures":
                llm_rate_limits,

            "validation_failures":
                llm_validation_failures,
        },

        "quality_metrics": {

            "llm_evaluated_examples":
                len(y_true_llm),

            "classifier_evaluated_examples":
                len(y_true_classifier),

            "llm":
                llm_metrics,

            "classifier":
                classifier_metrics,
        },

        "latency": {

            "llm_api":
                latency_stats(
                    llm_latencies
                ),

            "classifier_inference":
                latency_stats(
                    classifier_latencies
                ),
        },
    }

    # -------------------------------------------------------------
    # Save report
    # -------------------------------------------------------------

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
        )

    # -------------------------------------------------------------
    # Print final report
    # -------------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL COMPARISON REPORT")
    print("=" * 70)
    print()

    print("Dataset")
    print("-" * 70)

    print(
        "Total dataset examples :",
        len(dataset),
    )

    print(
        "Total test examples    :",
        len(test_indices),
    )

    print(
        "Examples evaluated     :",
        len(selected_indices),
    )

    print(
        "Number of labels       :",
        len(labels),
    )

    print()

    # -------------------------------------------------------------
    # LLM operational statistics
    # -------------------------------------------------------------

    print("LLM Operational Statistics")
    print("-" * 70)

    print(
        "LLM examples attempted       :",
        llm_attempted,
    )

    print(
        "LLM successful evaluations   :",
        llm_successful,
    )

    print(
        "LLM failed evaluations       :",
        llm_failed,
    )

    print(
        "LLM success rate             :",
        f"{llm_success_rate:.3f}",
    )

    print(
        "LLM failure rate             :",
        f"{llm_failure_rate:.3f}",
    )

    print(
        "LLM cache hits               :",
        llm_cache_hits,
    )

    print(
        "LLM cache hit rate           :",
        f"{llm_cache_hit_rate:.3f}",
    )

    print(
        "LLM API failures             :",
        llm_api_failures,
    )

    print(
        "LLM rate-limit failures      :",
        llm_rate_limits,
    )

    print(
        "LLM validation failures      :",
        llm_validation_failures,
    )

    # -------------------------------------------------------------
    # Quality metrics
    # -------------------------------------------------------------

    print()
    print("Quality Metrics")
    print("-" * 70)

    print(
        "LLM evaluated examples       :",
        len(y_true_llm),
    )

    print(
        "Classifier evaluated examples:",
        len(y_true_classifier),
    )

    # -------------------------------------------------------------
    # LLM metrics
    # -------------------------------------------------------------

    print()
    print("LLM")

    if llm_metrics is None:

        print(
            "  Micro precision : N/A"
        )

        print(
            "  Micro recall    : N/A"
        )

        print(
            "  Micro F1        : N/A"
        )

        print(
            "  Macro precision : N/A"
        )

        print(
            "  Macro recall    : N/A"
        )

        print(
            "  Macro F1        : N/A"
        )

        print(
            "  Weighted F1     : N/A"
        )

        print(
            "  Exact match     : N/A"
        )

        print(
            "  Hamming loss    : N/A"
        )

    else:

        print(
            "  Micro precision :",
            f"{llm_metrics['micro_precision']:.3f}",
        )

        print(
            "  Micro recall    :",
            f"{llm_metrics['micro_recall']:.3f}",
        )

        print(
            "  Micro F1        :",
            f"{llm_metrics['micro_f1']:.3f}",
        )

        print(
            "  Macro precision :",
            f"{llm_metrics['macro_precision']:.3f}",
        )

        print(
            "  Macro recall    :",
            f"{llm_metrics['macro_recall']:.3f}",
        )

        print(
            "  Macro F1        :",
            f"{llm_metrics['macro_f1']:.3f}",
        )

        print(
            "  Weighted F1     :",
            f"{llm_metrics['weighted_f1']:.3f}",
        )

        print(
            "  Exact match     :",
            f"{llm_metrics['exact_match']:.3f}",
        )

        print(
            "  Hamming loss    :",
            f"{llm_metrics['hamming_loss']:.3f}",
        )

    # -------------------------------------------------------------
    # Classifier metrics
    # -------------------------------------------------------------

    print()
    print("Classifier")

    print(
        "  Micro precision :",
        f"{classifier_metrics['micro_precision']:.3f}",
    )

    print(
        "  Micro recall    :",
        f"{classifier_metrics['micro_recall']:.3f}",
    )

    print(
        "  Micro F1        :",
        f"{classifier_metrics['micro_f1']:.3f}",
    )

    print(
        "  Macro precision :",
        f"{classifier_metrics['macro_precision']:.3f}",
    )

    print(
        "  Macro recall    :",
        f"{classifier_metrics['macro_recall']:.3f}",
    )

    print(
        "  Macro F1        :",
        f"{classifier_metrics['macro_f1']:.3f}",
    )

    print(
        "  Weighted F1     :",
        f"{classifier_metrics['weighted_f1']:.3f}",
    )

    print(
        "  Exact match     :",
        f"{classifier_metrics['exact_match']:.3f}",
    )

    print(
        "  Hamming loss    :",
        f"{classifier_metrics['hamming_loss']:.3f}",
    )

    # -------------------------------------------------------------
    # Latency
    # -------------------------------------------------------------

    print()
    print("Latency")
    print("-" * 70)

    llm_latency = latency_stats(
        llm_latencies
    )

    classifier_latency = latency_stats(
        classifier_latencies
    )

    if llm_latency is None:

        print(
            "LLM API latency: "
            "N/A (no successful uncached API calls)"
        )

    else:

        print(
            "LLM API latency"
        )

        print(
            "  Count   :",
            llm_latency["count"],
        )

        print(
            "  Average :",
            f"{llm_latency['average_ms']:.2f} ms",
        )

        print(
            "  Median  :",
            f"{llm_latency['median_ms']:.2f} ms",
        )

        print(
            "  P95     :",
            f"{llm_latency['p95_ms']:.2f} ms",
        )

    print()

    print(
        "Classifier inference latency"
    )

    print(
        "  Count   :",
        classifier_latency["count"],
    )

    print(
        "  Average :",
        f"{classifier_latency['average_ms']:.2f} ms",
    )

    print(
        "  Median  :",
        f"{classifier_latency['median_ms']:.2f} ms",
    )

    print(
        "  P95     :",
        f"{classifier_latency['p95_ms']:.2f} ms",
    )

    print()

    print("=" * 70)

    print(
        "Report saved to:"
    )

    print(REPORT_PATH)

    print(
        "Cache saved to:"
    )

    print(CACHE_PATH)

    print(
        "Test indices saved to:"
    )

    print(TEST_INDICES_PATH)

    print("=" * 70)


if __name__ == "__main__":
    main()