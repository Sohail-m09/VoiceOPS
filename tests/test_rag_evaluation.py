
import pytest

from voiceops.rag.evaluation import (
    evaluate_retrieval,
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    validate_k,
)


def test_recall_at_k():
    retrieved = ["chunk-1", "chunk-2", "chunk-3"]
    relevant = {"chunk-1", "chunk-3", "chunk-4"}

    assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 3)


def test_recall_at_k_finds_all_relevant_chunks():
    retrieved = ["chunk-1", "chunk-2", "chunk-3"]
    relevant = {"chunk-1", "chunk-3"}

    assert recall_at_k(retrieved, relevant, k=3) == 1.0


def test_reciprocal_rank_at_k():
    retrieved = ["chunk-1", "chunk-2", "chunk-3"]
    relevant = {"chunk-3"}

    assert reciprocal_rank_at_k(retrieved, relevant, k=3) == pytest.approx(
        1 / 3
    )


def test_reciprocal_rank_returns_zero_without_relevant_result():
    retrieved = ["chunk-1", "chunk-2"]
    relevant = {"chunk-3"}

    assert reciprocal_rank_at_k(retrieved, relevant, k=2) == 0.0


def test_hit_rate_at_k():
    retrieved = ["chunk-1", "chunk-2", "chunk-3"]
    relevant = {"chunk-3"}

    assert hit_rate_at_k(retrieved, relevant, k=3) == 1.0
    assert hit_rate_at_k(retrieved, relevant, k=2) == 0.0


def test_duplicate_results_do_not_distort_ranking():
    retrieved = ["chunk-1", "chunk-1", "chunk-2"]
    relevant = {"chunk-2"}

    assert reciprocal_rank_at_k(retrieved, relevant, k=3) == 0.5


@pytest.mark.parametrize("k", [0, -1, True, 1.5, "5"])
def test_invalid_k_is_rejected(k):
    with pytest.raises(ValueError):
        validate_k(k)


def test_evaluate_retrieval_calculates_aggregate_metrics():
    cases = [
        {
            "query": "How do I report damaged inventory?",
            "relevant_chunk_ids": {"chunk-1", "chunk-2"},
        },
        {
            "query": "How do I escalate a delayed shipment?",
            "relevant_chunk_ids": {"chunk-3"},
        },
    ]

    results = [
        [
            {"chunk_id": "chunk-1"},
            {"chunk_id": "chunk-4"},
            {"chunk_id": "chunk-2"},
        ],
        [
            {"chunk_id": "chunk-5"},
            {"chunk_id": "chunk-3"},
        ],
    ]

    report = evaluate_retrieval(cases, results, k=3)

    assert report["k"] == 3
    assert report["query_count"] == 2
    assert report["mean_recall_at_k"] == pytest.approx(1.0)
    assert report["mrr_at_k"] == pytest.approx((1.0 + 0.5) / 2)
    assert report["hit_rate_at_k"] == 1.0

    assert report["per_query"][0]["first_relevant_rank"] == 1
    assert report["per_query"][1]["first_relevant_rank"] == 2


def test_evaluate_retrieval_rejects_mismatched_result_count():
    cases = [
        {
            "query": "Damaged inventory procedure",
            "relevant_chunk_ids": {"chunk-1"},
        }
    ]

    with pytest.raises(ValueError):
        evaluate_retrieval(cases, [], k=5)


def test_evaluate_retrieval_rejects_empty_dataset():
    with pytest.raises(ValueError):
        evaluate_retrieval([], [], k=5)


def test_evaluate_retrieval_rejects_invalid_chunk_result():
    cases = [
        {
            "query": "Damaged inventory procedure",
            "relevant_chunk_ids": {"chunk-1"},
        }
    ]

    with pytest.raises(ValueError):
        evaluate_retrieval(cases, [[{"chunk_id": ""}]], k=5)
