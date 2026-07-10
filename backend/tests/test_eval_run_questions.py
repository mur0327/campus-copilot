import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from eval.run_questions import compute_metrics  # noqa: E402


@pytest.mark.parametrize(
    ("gold_rank", "expected"),
    [
        (1, 1.0),
        (3, 1 / math.log2(4)),
        (None, 0.0),
    ],
)
def test_compute_metrics_binary_ndcg_at_5(gold_rank: int | None, expected: float):
    metrics = compute_metrics(
        [
            {
                "id": "Q001",
                "answerability": "answerable",
                "has_gold": True,
                "gold_in_corpus": True,
                "gold_rank": gold_rank,
                "gold_rank_evidence": None,
                "gold_rank_semantic": None,
                "gold_rank_bm25": None,
            }
        ]
    )

    assert metrics["ndcg@5"] == pytest.approx(expected)
