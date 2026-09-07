"""Confidence scoring engine (spec §8.2).

Overall confidence is a weighted combination of six sub-scores:

  temporal_score            weight 0.15
  identity_score            weight 0.25
  location_score            weight 0.10
  source_corroboration      weight 0.25
  family_confirmation       weight 0.20
  semantic_consistency      weight 0.05
                            ------
                             1.00

Every sub-score is 0-100. Contradictions subtract up to 15 points
(-5 each, capped). The result is fully explainable: breakdown stores each
component, its weight, and its contribution, and explanation is a
human-readable summary — exactly what MemoryCard.confidence_breakdown and
MemoryCard.explanation are designed to hold.

Confidence bands (§8.2): 90-100 high, 75-89 good, 50-74 moderate,
25-49 low, 0-24 very_low.
"""

from app.models.constants import ConfidenceBand, DateAccuracy

# Weights from spec §8.2. Do not change without updating the spec mapping.
CONFIDENCE_WEIGHTS = {
    "temporal": 0.15,
    "identity": 0.25,
    "location": 0.10,
    "source_corroboration": 0.25,
    "family_confirmation": 0.20,
    "semantic_consistency": 0.05,
}

CONTRADICTION_PENALTY_PER_ITEM = 5.0
CONTRADICTION_PENALTY_CAP = 15.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def band_for(score: float) -> ConfidenceBand:
    """Map a 0-100 score to its spec §8.2 band."""
    if score >= 90:
        return ConfidenceBand.HIGH
    if score >= 75:
        return ConfidenceBand.GOOD
    if score >= 50:
        return ConfidenceBand.MODERATE
    if score >= 25:
        return ConfidenceBand.LOW
    return ConfidenceBand.VERY_LOW


def compute_confidence(
    sub_scores: dict[str, float],
    contradictions: list[str] | None = None,
) -> dict:
    """Compute the weighted overall score, breakdown, band, and explanation.

    sub_scores maps dimension names (CONFIDENCE_WEIGHTS keys) to 0-100
    values; missing dimensions count as 0.
    """
    contradictions = contradictions or []
    breakdown: dict[str, dict] = {}
    total = 0.0
    for dim, weight in CONFIDENCE_WEIGHTS.items():
        score = _clamp(sub_scores.get(dim, 0.0))
        contribution = score * weight
        breakdown[dim] = {
            "score": round(score, 1),
            "weight": weight,
            "contribution": round(contribution, 1),
        }
        total += contribution

    penalty = min(
        CONTRADICTION_PENALTY_CAP,
        CONTRADICTION_PENALTY_PER_ITEM * len(contradictions),
    )
    overall = round(max(0.0, min(100.0, total - penalty)), 1)

    return {
        "overall_score": overall,
        "band": band_for(overall).value,
        "breakdown": breakdown,
        "explanation": _build_explanation(breakdown, penalty, contradictions),
        "contradictions": contradictions,
        "penalty": round(penalty, 1),
    }


def _build_explanation(
    breakdown: dict[str, dict],
    penalty: float,
    contradictions: list[str],
) -> str:
    ordered = sorted(
        breakdown.values(),
        key=lambda b: b["contribution"],
        reverse=True,
    )
    strongest = ordered[0]
    weakest = ordered[-1]
    strong_dim = next(
        dim for dim, b in breakdown.items() if b is strongest
    )
    weak_dim = next(
        dim for dim, b in breakdown.items() if b is weakest
    )
    parts = [
        f"Overall confidence {sum(b['contribution'] for b in breakdown.values()):.1f}/100. "
        f"Strongest factor: {strong_dim} ({strongest['score']}/100 at weight {strongest['weight']}). "
        f"Weakest factor: {weak_dim} ({weakest['score']}/100 at weight {weakest['weight']})."
    ]
    if penalty:
        parts.append(f"{len(contradictions)} contradiction(s) reduced the score by {penalty:.1f} points.")
    if contradictions:
        parts.append("Contradictions: " + "; ".join(contradictions))
    return " ".join(parts)


# --------------------------------------------------------------------------
# Sub-score helpers. Each turns raw signals into a 0-100 score so the AI
# pipeline simulators (and eventually real extractors) stay simple.
# --------------------------------------------------------------------------


def temporal_score(date_accuracy: str | None) -> float:
    """How precisely the memory's date is known."""
    mapping = {
        DateAccuracy.EXACT.value: 100.0,
        DateAccuracy.DAY.value: 90.0,
        DateAccuracy.MONTH.value: 80.0,
        DateAccuracy.YEAR.value: 60.0,
        DateAccuracy.APPROXIMATE.value: 40.0,
    }
    return mapping.get(date_accuracy, 40.0)


def identity_score(face_confidence: float | None, identity_status: str | None = None) -> float:
    """How sure we are who the people in this memory are.

    face_confidence is the best face-match confidence (0-1); identity_status
    may be provided from the Person entity to override with reviewer input.
    """
    from app.models.constants import IdentityStatus

    if identity_status == IdentityStatus.FAMILY_CONFIRMED.value:
        return 95.0
    if identity_status == IdentityStatus.DISPUTED.value:
        return 10.0
    if identity_status == IdentityStatus.LIKELY_MATCH.value:
        return 80.0
    if identity_status == IdentityStatus.POSSIBLE_MATCH.value:
        return 55.0
    if face_confidence is None:
        return 20.0
    return _clamp(face_confidence * 100.0)


def location_score(has_exif: bool, has_context: bool) -> float:
    """How well the location is corroborated."""
    if has_exif:
        return 90.0
    if has_context:
        return 50.0
    return 10.0


def corroboration_score(independent_sources: int) -> float:
    """How many independent sources corroborate the memory."""
    if independent_sources >= 4:
        return 100.0
    if independent_sources == 3:
        return 90.0
    if independent_sources == 2:
        return 70.0
    if independent_sources == 1:
        return 40.0
    return 0.0


def family_confirmation_score(review_state: str | None) -> float:
    """Reviewer influence on confidence."""
    from app.models.constants import MemoryStatus

    approved = {MemoryStatus.APPROVED.value}
    if review_state in approved:
        return 95.0
    if review_state == MemoryStatus.DISPUTED.value:
        return 10.0
    if review_state == MemoryStatus.AWAITING_REVIEW.value:
        return 50.0
    return 30.0  # unreviewed draft


def semantic_consistency_score(consistency: float | None) -> float:
    """Internal consistency of the memory's claims (0-100).

    Callers (extractors/simulators) provide the signal; contradictions
    themselves are accounted for by the explicit penalty in
    compute_confidence, so they are not counted twice here.
    """
    if consistency is None:
        return 100.0
    return _clamp(consistency)


def score_from_signals(
    date_accuracy: str | None = None,
    face_confidence: float | None = None,
    identity_status: str | None = None,
    has_exif: bool = False,
    has_location_context: bool = False,
    independent_sources: int = 0,
    review_state: str | None = None,
    semantic_consistency: float | None = None,
    contradictions: list[str] | None = None,
) -> dict:
    """One-call convenience: raw signals in, full confidence result out.

    The AI pipeline simulators call this after gathering their signals.
    """
    return compute_confidence(
        {
            "temporal": temporal_score(date_accuracy),
            "identity": identity_score(face_confidence, identity_status),
            "location": location_score(has_exif, has_location_context),
            "source_corroboration": corroboration_score(independent_sources),
            "family_confirmation": family_confirmation_score(review_state),
            "semantic_consistency": semantic_consistency_score(semantic_consistency),
        },
        contradictions=contradictions,
    )
