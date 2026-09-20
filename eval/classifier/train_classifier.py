"""Train and evaluate a lightweight multi-label classifier.

Pipeline:
    free-text profile
        -> TF-IDF
        -> One-vs-Rest Logistic Regression
        -> scheme predictions

This is a classical-ML baseline for comparison against the LLM pipeline.

Important:
    - The classifier is NOT the production eligibility authority.
    - Ground-truth labels come from the deterministic rule engine used
      to generate the synthetic dataset.
    - Four production schemes are excluded from this experiment because
      they have no deterministic positive signal in the current synthetic
      rule representation.

Usage:
    python eval/classifier/train_classifier.py
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import (
    precision_recall_fscore_support,
    hamming_loss,
    accuracy_score,
)


def load_dataset(path: Path):
    """Load text + multilabel ground truth from JSONL dataset."""
    texts, label_sets = [], []

    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)

            if not row["text"]:
                continue

            texts.append(row["text"])
            label_sets.append(row["labels"])

    return texts, label_sets


def evaluate_predictions(Y_true, Y_pred, mlb):
    """Calculate aggregate and per-scheme metrics."""

    precision, recall, f1, support = precision_recall_fscore_support(
        Y_true,
        Y_pred,
        average=None,
        zero_division=0,
    )

    micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
        Y_true,
        Y_pred,
        average="micro",
        zero_division=0,
    )

    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        Y_true,
        Y_pred,
        average="macro",
        zero_division=0,
    )

    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        Y_true,
        Y_pred,
        average="weighted",
        zero_division=0,
    )

    exact_match = accuracy_score(Y_true, Y_pred)
    h_loss = hamming_loss(Y_true, Y_pred)

    per_scheme = {}

    for scheme_id, p, r, f, s in zip(
        mlb.classes_,
        precision,
        recall,
        f1,
        support,
    ):
        per_scheme[scheme_id] = {
            "precision": float(p),
            "recall": float(r),
            "f1": float(f),
            "support": int(s),
        }

    return {
        "micro_precision": float(micro_p),
        "micro_recall": float(micro_r),
        "micro_f1": float(micro_f1),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "weighted_precision": float(weighted_p),
        "weighted_recall": float(weighted_r),
        "weighted_f1": float(weighted_f1),
        "exact_match_accuracy": float(exact_match),
        "hamming_loss": float(h_loss),
        "per_scheme": per_scheme,
    }


def print_aggregate_metrics(metrics, title="Aggregate metrics"):
    """Print aggregate metrics."""

    print(f"\n=== {title} ===")

    print(
        "Micro  precision/recall/F1: "
        f"{metrics['micro_precision']:.3f} / "
        f"{metrics['micro_recall']:.3f} / "
        f"{metrics['micro_f1']:.3f}"
    )

    print(
        "Macro  precision/recall/F1: "
        f"{metrics['macro_precision']:.3f} / "
        f"{metrics['macro_recall']:.3f} / "
        f"{metrics['macro_f1']:.3f}"
    )

    print(
        "Weighted precision/recall/F1: "
        f"{metrics['weighted_precision']:.3f} / "
        f"{metrics['weighted_recall']:.3f} / "
        f"{metrics['weighted_f1']:.3f}"
    )

    print(
        "Exact label-set match accuracy: "
        f"{metrics['exact_match_accuracy']:.3f}"
    )

    print(
        "Hamming loss: "
        f"{metrics['hamming_loss']:.4f}"
    )


def print_per_scheme_metrics(metrics):
    """Print per-scheme metrics."""

    print("\n=== Per-scheme metrics ===")
    print(
        f"{'scheme_id':22s} "
        f"{'support':>7s} "
        f"{'precision':>10s} "
        f"{'recall':>8s} "
        f"{'f1':>6s}"
    )

    rows = []

    for scheme_id, values in metrics["per_scheme"].items():
        rows.append(
            (
                scheme_id,
                values["support"],
                values["precision"],
                values["recall"],
                values["f1"],
            )
        )

    for scheme_id, support, precision, recall, f1 in sorted(
        rows,
        key=lambda x: -x[1],
    ):
        print(
            f"{scheme_id:22s} "
            f"{support:7d} "
            f"{precision:10.2f} "
            f"{recall:8.2f} "
            f"{f1:6.2f}"
        )


def threshold_analysis(
    clf,
    X_test,
    Y_test,
    mlb,
    thresholds,
):
    """Evaluate different probability thresholds."""

    probabilities = clf.predict_proba(X_test)

    results = []

    print("\n=== Threshold analysis ===")
    print(
        f"{'threshold':>10s} "
        f"{'micro_F1':>10s} "
        f"{'macro_F1':>10s} "
        f"{'precision':>10s} "
        f"{'recall':>10s} "
        f"{'exact':>10s} "
        f"{'hamming':>10s}"
    )

    for threshold in thresholds:

        Y_pred = (probabilities >= threshold).astype(int)

        metrics = evaluate_predictions(
            Y_test,
            Y_pred,
            mlb,
        )

        row = {
            "threshold": float(threshold),
            **{
                key: value
                for key, value in metrics.items()
                if key != "per_scheme"
            },
        }

        results.append(row)

        print(
            f"{threshold:10.2f} "
            f"{metrics['micro_f1']:10.3f} "
            f"{metrics['macro_f1']:10.3f} "
            f"{metrics['micro_precision']:10.3f} "
            f"{metrics['micro_recall']:10.3f} "
            f"{metrics['exact_match_accuracy']:10.3f} "
            f"{metrics['hamming_loss']:10.4f}"
        )

    return results


def print_prediction_errors(
    clf,
    X_test,
    X_test_text,
    Y_test,
    mlb,
    threshold=0.5,
    max_examples=15,
):
    """Show examples where predicted and true label sets differ."""

    probabilities = clf.predict_proba(X_test)
    Y_pred = (probabilities >= threshold).astype(int)

    errors = []

    for i in range(len(X_test_text)):

        true_labels = set(
            mlb.inverse_transform(Y_test[i : i + 1])[0]
        )

        predicted_labels = set(
            mlb.inverse_transform(Y_pred[i : i + 1])[0]
        )

        if true_labels != predicted_labels:

            false_positive = predicted_labels - true_labels
            false_negative = true_labels - predicted_labels

            errors.append(
                {
                    "index": i,
                    "text": X_test_text[i],
                    "true": sorted(true_labels),
                    "predicted": sorted(predicted_labels),
                    "false_positive": sorted(false_positive),
                    "false_negative": sorted(false_negative),
                }
            )

    print(
        f"\n=== Prediction errors at threshold={threshold:.2f} "
        f"(showing up to {max_examples}) ==="
    )

    if not errors:
        print("No prediction errors found.")
        return errors

    for number, error in enumerate(errors[:max_examples], start=1):

        print(f"\n--- Error {number} ---")

        print(f"Text: {error['text']}")

        print(
            "True:       "
            + ", ".join(error["true"])
        )

        print(
            "Predicted:  "
            + ", ".join(error["predicted"])
        )

        if error["false_positive"]:
            print(
                "False +:    "
                + ", ".join(error["false_positive"])
            )

        if error["false_negative"]:
            print(
                "False -:    "
                + ", ".join(error["false_negative"])
            )

    return errors


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data",
        default="eval/classifier/synthetic_dataset.jsonl",
    )

    parser.add_argument(
        "--model-out",
        default="eval/classifier/model.pkl",
    )

    parser.add_argument(
        "--test-size",
        type=float,
        default=0.25,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    data_path = Path(args.data)

    if not data_path.exists():
        raise SystemExit(
            f"{data_path} not found -- "
            "run generate_synthetic_profiles.py first."
        )

    # ---------------------------------------------------------
    # 1. Load dataset
    # ---------------------------------------------------------

    texts, label_sets = load_dataset(data_path)

    print(f"Loaded {len(texts)} labeled examples.")

    n_empty = sum(
        1 for labels in label_sets if not labels
    )

    print(
        f"  {n_empty} examples have zero eligible schemes "
        "(kept in training)."
    )

    mlb = MultiLabelBinarizer()

    Y = mlb.fit_transform(label_sets)

    print(
        f"  {len(mlb.classes_)} distinct scheme_ids appear "
        f"as positive labels: {list(mlb.classes_)}"
    )

    # ---------------------------------------------------------
    # 2. Train/test split
    # ---------------------------------------------------------

    (
        X_train_text,
        X_test_text,
        Y_train,
        Y_test,
    ) = train_test_split(
        texts,
        Y,
        test_size=args.test_size,
        random_state=args.seed,
    )

    print(
        f"\nTrain examples: {len(X_train_text)}"
    )

    print(
        f"Test examples:  {len(X_test_text)}"
    )

    # ---------------------------------------------------------
    # 3. TF-IDF
    # ---------------------------------------------------------

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_features=5000,
        sublinear_tf=True,
    )

    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    print(
        f"\nTF-IDF features: {X_train.shape[1]}"
    )

    # ---------------------------------------------------------
    # 4. One-vs-Rest Logistic Regression
    # ---------------------------------------------------------

    clf = OneVsRestClassifier(
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=args.seed,
        )
    )

    clf.fit(
        X_train,
        Y_train,
    )

    # ---------------------------------------------------------
    # 5. Baseline at threshold 0.5
    # ---------------------------------------------------------

    Y_pred = clf.predict(X_test)

    baseline_metrics = evaluate_predictions(
        Y_test,
        Y_pred,
        mlb,
    )

    print_per_scheme_metrics(
        baseline_metrics
    )

    print_aggregate_metrics(
        baseline_metrics,
        "Baseline aggregate metrics (threshold=0.5)",
    )

    # ---------------------------------------------------------
    # 6. Threshold analysis
    # ---------------------------------------------------------

    thresholds = [
        0.30,
        0.40,
        0.50,
        0.60,
        0.70,
        0.80,
    ]

    threshold_results = threshold_analysis(
        clf,
        X_test,
        Y_test,
        mlb,
        thresholds,
    )

    # Find threshold with highest micro-F1.
    # This is reported for analysis only; it is NOT automatically
    # adopted as the production threshold.
    best_threshold = max(
        threshold_results,
        key=lambda row: row["micro_f1"],
    )

    print(
        "\nBest threshold by micro-F1 on this test split: "
        f"{best_threshold['threshold']:.2f}"
    )

    print(
        f"Micro-F1: {best_threshold['micro_f1']:.3f}"
    )

    # ---------------------------------------------------------
    # 7. Error analysis
    # ---------------------------------------------------------

    errors = print_prediction_errors(
        clf,
        X_test,
        X_test_text,
        Y_test,
        mlb,
        threshold=0.5,
        max_examples=15,
    )

    # ---------------------------------------------------------
    # 8. Save trained pipeline
    # ---------------------------------------------------------

    model_out = Path(args.model_out)

    model_out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with model_out.open("wb") as f:

        pickle.dump(
            {
                "vectorizer": vectorizer,
                "classifier": clf,
                "mlb": mlb,
            },
            f,
        )

    print(
        f"\nSaved trained pipeline to {model_out}"
    )

    # ---------------------------------------------------------
    # 9. Save metrics
    # ---------------------------------------------------------

    metrics_out = model_out.with_suffix(
        ".metrics.json"
    )

    output = {
        "dataset": str(data_path),
        "n_examples": len(texts),
        "n_train": len(X_train_text),
        "n_test": len(X_test_text),
        "n_labels": len(mlb.classes_),
        "labels": list(mlb.classes_),
        "baseline_threshold": 0.5,
        "baseline": baseline_metrics,
        "threshold_analysis": threshold_results,
        "best_threshold_by_micro_f1": best_threshold,
        "error_count_at_0_5": len(errors),
    }

    with metrics_out.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )

    print(
        f"Saved metrics to {metrics_out}"
    )


if __name__ == "__main__":
    main()

