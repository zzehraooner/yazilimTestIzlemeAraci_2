from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/runs", tags=["samples"])


@router.post("/{run_id}/samples", status_code=status.HTTP_204_NO_CONTENT)
def ingest_samples(run_id: int, samples: List[schemas.MetricSampleIn], db: Session = Depends(get_db)):
    if not samples:
        return

    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add samples to a finished run")

    entities = []
    for sample in samples:
        ts = datetime.fromtimestamp(sample.ts, tz=timezone.utc)
        entities.append(
            models.MetricSample(
                run_id=run_id,
                ts=ts,
                cpu_percent=sample.cpu_percent,
                rss_mb=sample.rss_mb,
            )
        )

    db.bulk_save_objects(entities)
    db.commit()


@router.get("/{run_id}/samples", response_model=schemas.RunSamplesResponse)
def get_samples(
    run_id: int,
    downsample: bool = Query(False),
    step: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    query = (
        db.query(models.MetricSample)
        .filter(models.MetricSample.run_id == run_id)
        .order_by(models.MetricSample.ts.asc())
    )
    all_samples = query.all()

    if downsample and step > 1:
        filtered = all_samples[::step]
    else:
        filtered = all_samples

    serialized = [
        schemas.MetricSampleIn(
            ts=sample.ts.timestamp(),
            cpu_percent=sample.cpu_percent,
            rss_mb=sample.rss_mb,
        )
        for sample in filtered
    ]

    return schemas.RunSamplesResponse(samples=serialized)
