from __future__ import annotations
from typing import Any
from app.schemas.output_schema import EvidenceCard


def build_evidence_cards(snapshot: dict[str, Any]) -> list[EvidenceCard]:
    metrics = snapshot.get("metrics", {})
    cards: list[EvidenceCard] = []
    for metric, info in metrics.items():
        latest = info.get("latest")
        previous = info.get("previous")
        change_pct = info.get("change_pct")
        detail = f"latest={latest}"
        if previous is not None:
            detail += f", previous={previous}"
        if change_pct is not None:
            detail += f", change={change_pct:.2%}"
        cards.append(
            EvidenceCard(
                title=f"{metric} trend",
                detail=detail,
                metric=metric,
                window_days=snapshot.get("window_days"),
            )
        )
    return cards
