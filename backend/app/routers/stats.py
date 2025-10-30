from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..db import get_db
from .runs import map_run_summary

router = APIRouter(tags=["stats"])


@router.get("/compare", response_model=schemas.ComparisonResponse)
def compare_runs(
    current: int = Query(..., description="Run id to compare"),
    baseline: Optional[str] = Query("latest-success", description="Baseline run id or 'latest-success'"),
    db: Session = Depends(get_db),
):
    current_run = (
        db.query(models.TestRun)
        .options(joinedload(models.TestRun.stats))
        .filter(models.TestRun.id == current)
        .first()
    )
    if current_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current run not found")
    if current_run.stats is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current run has no stats yet")

    baseline_run = resolve_baseline(db, baseline, exclude_run_id=current_run.id)
    if baseline_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline run not found")
    if baseline_run.stats is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Baseline run has no stats yet")

    current_stats = current_run.stats
    baseline_stats = baseline_run.stats

    messages: List[str] = []
    messages.append(
        format_cpu_message(
            "ort. CPU",
            baseline_stats.avg_cpu,
            current_stats.avg_cpu,
        )
    )
    messages.append(
        format_cpu_message(
            "p95 CPU",
            baseline_stats.p95_cpu,
            current_stats.p95_cpu,
        )
    )
    messages.append(
        format_cpu_message(
            "maks. CPU",
            baseline_stats.max_cpu,
            current_stats.max_cpu,
        )
    )
    messages.append(
        format_ram_message(
            "ort. RAM",
            baseline_stats.avg_rss_mb,
            current_stats.avg_rss_mb,
        )
    )
    messages.append(
        format_ram_message(
            "p95 RAM",
            baseline_stats.p95_rss_mb,
            current_stats.p95_rss_mb,
        )
    )

    if current_stats.avg_cpu is not None and current_stats.avg_cpu > 80:
        messages.append("Uyarı: Ortalama CPU %80 üzerinde, yüksek yük tespit edildi.")

    return schemas.ComparisonResponse(
        current_run=map_run_summary(current_run),
        baseline_run=map_run_summary(baseline_run),
        messages=[msg for msg in messages if msg],
    )


def resolve_baseline(db: Session, baseline: Optional[str], exclude_run_id: Optional[int]) -> Optional[models.TestRun]:
    query = db.query(models.TestRun).options(joinedload(models.TestRun.stats))
    if baseline is None or baseline == "latest-success":
        q = (
            query.filter(models.TestRun.status == "completed")
            .order_by(models.TestRun.ended_at.desc())
        )
        if exclude_run_id is not None:
            q = q.filter(models.TestRun.id != exclude_run_id)
        return q.first()
    try:
        run_id = int(baseline)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid baseline id") from exc
    return query.filter(models.TestRun.id == run_id).first()


def format_cpu_message(label: str, base: Optional[float], current: Optional[float]) -> Optional[str]:
    if base is None or current is None:
        return None
    delta = current - base
    relative = (delta / base * 100) if base else float("inf")
    if np.isinf(relative):
        relative_str = "∞"
    else:
        relative_str = f"{relative:.0f}"
    return (
        f"Önceki koşunun {label}'su **%{base:.1f}**, bu koşunun **%{current:.1f}**. "
        f"Fark **{delta:.1f} pp** (~%{relative_str})."
    )


def format_ram_message(label: str, base: Optional[float], current: Optional[float]) -> Optional[str]:
    if base is None or current is None:
        return None
    delta = current - base
    relative = (delta / base * 100) if base else float("inf")
    if np.isinf(relative):
        relative_str = "∞"
    else:
        relative_str = f"{relative:.0f}"
    return (
        f"Önceki koşunun {label}'ı **{base:.1f} MB**, bu koşunun **{current:.1f} MB**. "
        f"Fark **{delta:.1f} MB** (~%{relative_str})."
    )
