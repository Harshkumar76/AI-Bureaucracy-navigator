"""
tests/test_metrics.py

Pure unit tests for eval/metrics.py -- no database needed.
"""
import pytest
from eval.metrics import precision_at_k, recall_at_k, reciprocal_rank, hit_rate


def test_precision_at_k_all_relevant():
    assert precision_at_k(["a", "b", "c"], {"a", "b", "c"}, 3) == 1.0


def test_precision_at_k_none_relevant():
    assert precision_at_k(["x", "y"], {"a", "b"}, 2) == 0.0


def test_precision_at_k_partial():
    assert precision_at_k(["a", "x", "b"], {"a", "b"}, 3) == pytest.approx(2 / 3)


def test_recall_at_k_finds_all():
    assert recall_at_k(["a", "b"], {"a", "b"}, 2) == 1.0


def test_recall_at_k_misses_some():
    assert recall_at_k(["a"], {"a", "b"}, 1) == 0.5


def test_recall_at_k_no_relevant_expected_is_vacuously_perfect():
    assert recall_at_k(["a", "b"], set(), 2) == 1.0


def test_reciprocal_rank_first_position():
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0


def test_reciprocal_rank_second_position():
    assert reciprocal_rank(["x", "a"], {"a"}) == 0.5


def test_reciprocal_rank_not_found():
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_hit_rate_true():
    assert hit_rate(["x", "a"], {"a"}, 2) == 1.0


def test_hit_rate_false():
    assert hit_rate(["x", "y"], {"a"}, 2) == 0.0