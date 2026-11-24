
from typing import Any


def validate_k(k: int) -> None:
    """Validate the number of top results to evaluate."""

    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("K must be a positive integer.")


def validate_chunk_ids(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
) -> None:
    """Validate retrieved and relevant chunk identifiers."""

    if not isinstance(retrieved_chunk_ids, list):
        raise ValueError("Retrieved chunk IDs must be a list.")

    if not all(
        isinstance(chunk_id, str) and chunk_id.strip()
        for chunk_id in retrieved_chunk_ids
    ):
        raise ValueError("Retrieved chunk IDs must be non-empty strings.")

    if not isinstance(relevant_chunk_ids, set) or not relevant_chunk_ids:
        raise ValueError("Relevant chunk IDs must be a non-empty set.")

    if not all(
        isinstance(chunk_id, str) and chunk_id.strip()
        for chunk_id in relevant_chunk_ids
    ):
        raise ValueError("Relevant chunk IDs must be non-empty strings.")


def _unique_in_order(chunk_ids: list[str]) -> list[str]:
    """Remove duplicate IDs while preserving their ranking order."""

    return list(dict.fromkeys(chunk_ids))


def recall_at_k(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
    k: int = 5,
) -> float:
    """Calculate the fraction of relevant chunks found in top K."""

    validate_k(k)
    validate_chunk_ids(retrieved_chunk_ids, relevant_chunk_ids)

    top_results = set(_unique_in_order(retrieved_chunk_ids)[:k])
    relevant_found = top_results.intersection(relevant_chunk_ids)

    return len(relevant_found) / len(relevant_chunk_ids)


def reciprocal_rank_at_k(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
    k: int = 5,
) -> float:
    """Calculate the reciprocal rank of the first relevant result."""

    validate_k(k)
    validate_chunk_ids(retrieved_chunk_ids, relevant_chunk_ids)

    unique_results = _unique_in_order(retrieved_chunk_ids)

    for rank, chunk_id in enumerate(unique_results[:k], start=1):
        if chunk_id in relevant_chunk_ids:
            return 1.0 / rank

    return 0.0


def hit_rate_at_k(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
    k: int = 5,
) -> float:
    """Return 1 when at least one relevant chunk appears in top K."""

    validate_k(k)
    validate_chunk_ids(retrieved_chunk_ids, relevant_chunk_ids)

    top_results = set(_unique_in_order(retrieved_chunk_ids)[:k])

    return float(bool(top_results.intersection(relevant_chunk_ids)))


def evaluate_retrieval(
    evaluation_cases: list[dict[str, Any]],
    retrieval_results: list[list[dict[str, Any]]],
    k: int = 5,
) -> dict[str, Any]:
    """Evaluate ranked retrieval results against known relevant chunks."""

    validate_k(k)

    if not isinstance(evaluation_cases, list) or not evaluation_cases:
        raise ValueError("Evaluation cases must be a non-empty list.")

    if not isinstance(retrieval_results, list):
        raise ValueError("Retrieval results must be a list.")

    if len(evaluation_cases) != len(retrieval_results):
        raise ValueError(
            "Each evaluation case must have corresponding retrieval results."
        )

    per_query: list[dict[str, Any]] = []

    for case, results in zip(evaluation_cases, retrieval_results):
        if not isinstance(case, dict):
            raise ValueError("Each evaluation case must be a dictionary.")

        query = case.get("query")
        relevant_ids = case.get("relevant_chunk_ids")

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Each evaluation case needs a valid query.")

        if not isinstance(relevant_ids, set) or not relevant_ids:
            raise ValueError(
                "Each evaluation case needs relevant chunk IDs as a set."
            )

        if not isinstance(results, list):
            raise ValueError("Each retrieval result must be a list.")

        retrieved_ids: list[str] = []

        for result in results:
            if not isinstance(result, dict):
                raise ValueError("Each retrieved result must be a dictionary.")

            chunk_id = result.get("chunk_id")

            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError(
                    "Each retrieved result needs a valid chunk ID."
                )

            retrieved_ids.append(chunk_id)

        recall = recall_at_k(retrieved_ids, relevant_ids, k)
        reciprocal_rank = reciprocal_rank_at_k(
            retrieved_ids,
            relevant_ids,
            k,
        )
        hit_rate = hit_rate_at_k(retrieved_ids, relevant_ids, k)

        unique_results = _unique_in_order(retrieved_ids)

        first_relevant_rank = next(
            (
                rank
                for rank, chunk_id in enumerate(unique_results[:k], start=1)
                if chunk_id in relevant_ids
            ),
            None,
        )

        per_query.append({
            "query": query,
            "retrieved_count": len(unique_results),
            "relevant_count": len(relevant_ids),
            "first_relevant_rank": first_relevant_rank,
            "recall_at_k": recall,
            "reciprocal_rank_at_k": reciprocal_rank,
            "hit_rate_at_k": hit_rate,
        })

    query_count = len(per_query)

    return {
        "k": k,
        "query_count": query_count,
        "mean_recall_at_k": (
            sum(item["recall_at_k"] for item in per_query) / query_count
        ),
        "mrr_at_k": (
            sum(
                item["reciprocal_rank_at_k"]
                for item in per_query
            ) / query_count
        ),
        "hit_rate_at_k": (
            sum(item["hit_rate_at_k"] for item in per_query) / query_count
        ),
        "per_query": per_query,
    }
