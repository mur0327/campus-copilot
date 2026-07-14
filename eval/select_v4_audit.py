"""qrel v4 B2 사람 감사용 질문-페이지 묶음을 재현 가능하게 선정한다.

선정에는 LLM 초벌 라벨을 사용하지만 출력에는 행 ID와 비식별 집계만 남긴다.
검토자는 초기 라벨, 선정 사유, 검색 모드·순위·점수를 보지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.make_v4_pool import RETRIEVAL_PATHS, load_jsonl, top_k_items  # noqa: E402
from eval.run_questions import normalize_url  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
PRIMARY_PATH = EVAL_DIR / "qrel-v4-primary-initial.json"
QUESTIONS_PATH = EVAL_DIR / "questions.csv"
V3_PAGES_PATH = EVAL_DIR / "gold_sources_v3.csv"
DEFAULT_OUT_PATH = REPO_ROOT / "tmp" / "qrel-v4" / "b2-pilot-ids.txt"

PILOT_SEED = "qrel-v4-b2-20260714"
PILOT_BUNDLE_COUNT = 10
POSITIVE_GRADES = frozenset({"full", "partial"})
BOUNDARY_PREFIX = "경계:"
CONFLICT_TOKENS = ("충돌", "상충")
SPECIAL_DOCUMENT_TOKENS = (
    ".pdf",
    "pdfdownload",
    "transpdf",
    "이미지",
    "image",
    "canvas",
)

# 코드북 §9에서 페이지 행 자체가 사전 쟁점으로 고정된 사례다. 질문 수준 변경은
# 페이지 감사·조정 뒤 50문항 전량 검토 단계에서 별도로 확인한다.
KNOWN_CHANGED_PAGES = frozenset(
    {
        ("Q030", "https://beauty.honam.ac.kr/DepartmentNotice/1/read/236"),
        ("Q030", "https://www.honam.ac.kr/Scholarship_SchFees/1/read/5254"),
        ("Q033", "https://www.honam.ac.kr/GradesRecognition"),
        ("Q037", "https://dreamlife.honam.ac.kr/FrequentlyQuestions/1/read/29"),
        ("Q041", "https://www.honam.ac.kr/SeasonSemester"),
    }
)
KNOWN_CHANGED_PAGE_KEYS = frozenset(
    (question_id, normalize_url(url)) for question_id, url in KNOWN_CHANGED_PAGES
)

# 초벌 동결 뒤 자동 정합성 재확인 대상으로 확인된 문항이다. 기존 판정을 바꾸지
# 않고, 대체 근거 존재 여부를 한 질문 안에서 함께 보도록 전 묶음을 표적 감사한다.
INVARIANT_CANDIDATE_QUESTION_IDS = frozenset({"Q030"})


@dataclass(frozen=True)
class Exposure:
    mode: str
    rank: int
    source_scope: str
    page_kind: str


@dataclass(frozen=True)
class AuditBundle:
    question_id: str
    canonical_url: str
    page_row_id: str
    evidence_row_ids: tuple[str, ...]
    label_class: str
    rank_band: str
    mode_presence: str
    document_kind: str
    question_type: str
    source_scope: str
    target_reasons: frozenset[str]

    @property
    def audit_track(self) -> str:
        return "targeted" if self.target_reasons else "sample"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return [dict(row) for row in csv.DictReader(input_file)]


def load_primary(path: Path = PRIMARY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    incomplete = [
        row["row_id"]
        for section in ("pages", "evidence", "questions")
        for row in payload[section]
        if not row["judged"]
    ]
    if incomplete:
        raise ValueError(f"초벌 판정에 미완료 행이 있습니다: {incomplete[0]}")
    return payload


def load_exposures(
    retrieval_paths: tuple[Path, ...] = RETRIEVAL_PATHS,
) -> dict[tuple[str, str], tuple[Exposure, ...]]:
    by_bundle: dict[tuple[str, str], list[Exposure]] = defaultdict(list)
    for path in retrieval_paths:
        mode = path.name.split("-")[1]
        for row in load_jsonl(path):
            for item in top_k_items(row):
                key = (row["id"], normalize_url(item["url"]))
                by_bundle[key].append(
                    Exposure(
                        mode=mode,
                        rank=int(item["rank"]),
                        source_scope=str(item.get("source_scope") or ""),
                        page_kind=str(item.get("page_kind") or ""),
                    )
                )
    return {key: tuple(value) for key, value in by_bundle.items()}


def _rank_band(exposures: tuple[Exposure, ...]) -> str:
    if not exposures:
        return "unranked"
    return "1-2" if min(item.rank for item in exposures) <= 2 else "3-5"


def _mode_presence(exposures: tuple[Exposure, ...]) -> str:
    mode_count = len({item.mode for item in exposures})
    if mode_count == 0:
        return "unranked"
    return "single" if mode_count == 1 else "multiple"


def _dominant_value(values: list[str], fallback: str) -> str:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        if value:
            counts[value] += 1
    if not counts:
        return fallback
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def _document_kind(
    canonical_url: str,
    page_notes: str,
    evidence_notes: list[str],
    exposures: tuple[Exposure, ...],
) -> str:
    searchable = " ".join(
        [
            canonical_url,
            page_notes,
            *evidence_notes,
            *(item.page_kind for item in exposures),
        ]
    ).lower()
    return (
        "special"
        if any(token.lower() in searchable for token in SPECIAL_DOCUMENT_TOKENS)
        else "general"
    )


def _v3_page_axes() -> dict[tuple[str, str], tuple[str, str, str]]:
    return {
        (row["question_id"], normalize_url(row["gold_url"])): (
            row["support_grade"],
            row["temporal_validity"],
            row["audience_scope"],
        )
        for row in load_csv(V3_PAGES_PATH)
    }


def build_bundles(
    primary: dict[str, Any],
    *,
    exposures: dict[tuple[str, str], tuple[Exposure, ...]] | None = None,
) -> list[AuditBundle]:
    exposures = exposures if exposures is not None else load_exposures()
    questions = {row["id"]: row for row in load_csv(QUESTIONS_PATH)}
    question_rows = {row["question_id"]: row for row in primary["questions"]}
    v3_axes = _v3_page_axes()

    evidence_by_bundle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in primary["evidence"]:
        key = (row["question_id"], normalize_url(row["canonical_url"]))
        evidence_by_bundle[key].append(row)

    bundles: list[AuditBundle] = []
    for page in primary["pages"]:
        question_id = page["question_id"]
        canonical_url = normalize_url(page["canonical_url"])
        key = (question_id, canonical_url)
        evidence_rows = evidence_by_bundle[key]
        question_row = question_rows[question_id]
        bundle_exposures = exposures.get(key, ())
        target_reasons: set[str] = set()

        page_notes = str(page.get("notes") or "")
        evidence_notes = [str(row.get("notes") or "") for row in evidence_rows]
        bundle_notes = [page_notes, *evidence_notes]

        if any(note.lstrip().startswith(BOUNDARY_PREFIX) for note in bundle_notes):
            target_reasons.add("boundary")
        if any(token in note for note in bundle_notes for token in CONFLICT_TOKENS):
            target_reasons.add("conflict")

        current_axes = (
            page["support_grade"],
            page["temporal_validity"],
            page["audience_scope"],
        )
        if key in v3_axes and v3_axes[key] != current_axes:
            target_reasons.add("v3-v4-change")
        if key in KNOWN_CHANGED_PAGE_KEYS:
            target_reasons.add("codebook-case")

        deployment_sensitive = (
            question_row["expected_behavior"] != "full_answer"
            and page["support_grade"] in POSITIVE_GRADES
            and (
                page["temporal_validity"] != "current"
                or page["audience_scope"] != "match"
            )
        )
        if deployment_sensitive:
            target_reasons.add("deployment-sensitive")

        if question_id in INVARIANT_CANDIDATE_QUESTION_IDS:
            target_reasons.add("invariant-candidate")

        composition_sources = {
            normalize_url(url) for url in question_row.get("composition_sources", [])
        }
        if (
            question_row.get("composition_override")
            and canonical_url in composition_sources
        ):
            target_reasons.add("composition")

        source_scope = _dominant_value(
            [item.source_scope for item in bundle_exposures],
            "seed",
        )
        bundles.append(
            AuditBundle(
                question_id=question_id,
                canonical_url=canonical_url,
                page_row_id=page["row_id"],
                evidence_row_ids=tuple(sorted(row["row_id"] for row in evidence_rows)),
                label_class=(
                    "positive"
                    if page["support_grade"] in POSITIVE_GRADES
                    else "invalid"
                ),
                rank_band=_rank_band(bundle_exposures),
                mode_presence=_mode_presence(bundle_exposures),
                document_kind=_document_kind(
                    canonical_url,
                    page_notes,
                    evidence_notes,
                    bundle_exposures,
                ),
                question_type=questions[question_id]["question_type"],
                source_scope=source_scope,
                target_reasons=frozenset(target_reasons),
            )
        )
    return bundles


def stable_bundle_hash(bundle: AuditBundle, seed: str) -> str:
    value = f"{bundle.question_id}|{bundle.canonical_url}|{seed}"
    return hashlib.sha256(value.encode()).hexdigest()


def _pick_diverse(
    candidates: list[AuditBundle],
    count: int,
    *,
    seed: str,
    already_selected: set[tuple[str, str]] | None = None,
) -> list[AuditBundle]:
    selected: list[AuditBundle] = []
    selected_keys = set(already_selected or set())
    covered: dict[str, set[str]] = defaultdict(set)
    dimensions = (
        "rank_band",
        "mode_presence",
        "document_kind",
        "audit_track",
        "question_type",
        "source_scope",
    )

    while len(selected) < count:
        available = [
            bundle
            for bundle in candidates
            if (bundle.question_id, bundle.canonical_url) not in selected_keys
        ]
        if not available:
            break

        def priority(bundle: AuditBundle) -> tuple[int, int, str]:
            unseen_question = bundle.question_id not in covered["question_id"]
            new_values = sum(
                getattr(bundle, dimension) not in covered[dimension]
                for dimension in dimensions
            )
            return (
                -int(unseen_question),
                -new_values,
                stable_bundle_hash(bundle, seed),
            )

        chosen = min(available, key=priority)
        selected.append(chosen)
        selected_keys.add((chosen.question_id, chosen.canonical_url))
        covered["question_id"].add(chosen.question_id)
        for dimension in dimensions:
            covered[dimension].add(getattr(chosen, dimension))

    if len(selected) != count:
        raise ValueError(
            f"요청한 {count}개 묶음 중 {len(selected)}개만 선정할 수 있습니다"
        )
    return selected


def select_stratified_bundles(
    bundles: list[AuditBundle],
    count: int,
    *,
    seed: str = PILOT_SEED,
) -> list[AuditBundle]:
    if count < 2:
        raise ValueError(
            "양성과 invalid를 모두 포함하려면 묶음 수가 2개 이상이어야 합니다"
        )

    positive_count = count // 2
    invalid_count = count - positive_count
    positive = [bundle for bundle in bundles if bundle.label_class == "positive"]
    invalid = [bundle for bundle in bundles if bundle.label_class == "invalid"]

    selected = _pick_diverse(positive, positive_count, seed=f"{seed}|positive")
    selected.extend(
        _pick_diverse(
            invalid,
            invalid_count,
            seed=f"{seed}|invalid",
            already_selected={
                (bundle.question_id, bundle.canonical_url) for bundle in selected
            },
        )
    )
    return sorted(
        selected, key=lambda bundle: (bundle.question_id, bundle.canonical_url)
    )


def select_full_audit_bundles(
    bundles: list[AuditBundle],
    sample_count: int,
    *,
    seed: str = PILOT_SEED,
) -> tuple[list[AuditBundle], int]:
    targeted = [bundle for bundle in bundles if bundle.target_reasons]
    targeted_keys = {(bundle.question_id, bundle.canonical_url) for bundle in targeted}
    pilot = select_stratified_bundles(bundles, PILOT_BUNDLE_COUNT, seed=seed)
    pilot_sampled = [
        bundle
        for bundle in pilot
        if (bundle.question_id, bundle.canonical_url) not in targeted_keys
    ]
    if sample_count < len(pilot_sampled):
        raise ValueError(
            f"최종 표본 {sample_count}개로는 파일럿의 비표적 묶음 "
            f"{len(pilot_sampled)}개를 모두 포함할 수 없습니다"
        )
    pilot_sampled_keys = {
        (bundle.question_id, bundle.canonical_url) for bundle in pilot_sampled
    }
    remaining = [
        bundle
        for bundle in bundles
        if (bundle.question_id, bundle.canonical_url) not in targeted_keys
        and (bundle.question_id, bundle.canonical_url) not in pilot_sampled_keys
    ]
    additional_count = sample_count - len(pilot_sampled)
    if additional_count == 1:
        additional = _pick_diverse(remaining, 1, seed=f"{seed}|full")
    elif additional_count > 1:
        additional = select_stratified_bundles(
            remaining,
            additional_count,
            seed=f"{seed}|full",
        )
    else:
        additional = []
    sampled = [*pilot_sampled, *additional]
    combined = sorted(
        [*targeted, *sampled],
        key=lambda bundle: (bundle.question_id, bundle.canonical_url),
    )
    return combined, len(targeted)


def audit_row_ids(bundles: list[AuditBundle]) -> list[str]:
    row_ids: list[str] = []
    for bundle in bundles:
        row_ids.append(bundle.page_row_id)
        row_ids.extend(bundle.evidence_row_ids)
    return row_ids


def render_ids_file(
    bundles: list[AuditBundle],
    *,
    phase: str,
    seed: str,
    targeted_count: int | None = None,
) -> str:
    row_ids = audit_row_ids(bundles)
    evidence_count = sum(len(bundle.evidence_row_ids) for bundle in bundles)
    selection_hash = hashlib.sha256("\n".join(row_ids).encode()).hexdigest()
    comments = [
        "# qrel v4 B2 author-audit IDs",
        f"# phase={phase}",
        f"# seed={seed}",
        f"# bundle_count={len(bundles)}",
        f"# page_controls={len(bundles)}",
        f"# evidence_controls={evidence_count}",
        "# question_controls=0",
    ]
    if targeted_count is not None:
        comments.extend(
            [
                f"# targeted_bundle_count={targeted_count}",
                f"# sampled_bundle_count={len(bundles) - targeted_count}",
            ]
        )
    comments.append(f"# selection_sha256={selection_hash}")
    return "\n".join([*comments, *row_ids, ""])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="qrel v4 B2 사람 감사 묶음을 선정합니다."
    )
    parser.add_argument("--phase", choices=("pilot", "full"), default="pilot")
    parser.add_argument(
        "--bundle-count",
        type=int,
        default=10,
        help="pilot 묶음 수 또는 full 단계의 비표적 표본 묶음 수",
    )
    parser.add_argument("--seed", default=PILOT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundles = build_bundles(load_primary())
    if args.phase == "pilot":
        selected = select_stratified_bundles(bundles, args.bundle_count, seed=args.seed)
        targeted_count = None
    else:
        selected, targeted_count = select_full_audit_bundles(
            bundles,
            args.bundle_count,
            seed=args.seed,
        )

    content = render_ids_file(
        selected,
        phase=args.phase,
        seed=args.seed,
        targeted_count=targeted_count,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    evidence_count = sum(len(bundle.evidence_row_ids) for bundle in selected)
    print(f"저장: {args.out}")
    print(
        f"감사 묶음 {len(selected)}개 "
        f"(페이지 {len(selected)}행, evidence {evidence_count}행)"
    )
    print(f"선정 시드: {args.seed}")


if __name__ == "__main__":
    main()
