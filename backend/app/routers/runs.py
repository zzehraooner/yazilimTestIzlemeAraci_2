from datetime import datetime, timezone
from typing import List

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=schemas.RunCreateResponse, status_code=status.HTTP_201_CREATED)
def create_run(payload: schemas.RunCreate, db: Session = Depends(get_db)):
    command = payload.command.strip()
    if not command:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Command cannot be empty")

    run = models.TestRun(command=command, baseline_run_id=payload.baseline_run_id)
    db.add(run)
    db.commit()
    db.refresh(run)
    return schemas.RunCreateResponse(id=run.id, started_at=run.started_at)


@router.get("", response_model=List[schemas.RunSummary])
def list_runs(db: Session = Depends(get_db)):
    runs = (
        db.query(models.TestRun)
        .options(joinedload(models.TestRun.stats))
        .order_by(models.TestRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [map_run_summary(run) for run in runs]


@router.get("/{run_id}", response_model=schemas.RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(models.TestRun)
        .options(joinedload(models.TestRun.stats), joinedload(models.TestRun.samples))
        .filter(models.TestRun.id == run_id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return map_run_detail(run)


@router.patch("/{run_id}/finish", response_model=schemas.RunDetail)
def finish_run(run_id: int, payload: schemas.RunFinishRequest, db: Session = Depends(get_db)):
    # --- DÜZELTME BÖLÜM 1: KİLİTLE VE GÜNCELLE ---
    
    # 1. Önce SADECE ana satırı çek ve KİLİTLE (JOIN YOK)
    run_to_update: models.TestRun | None = (
        db.query(models.TestRun)
        .filter(models.TestRun.id == run_id)
        .with_for_update()
        .one_or_none()
    )
    
    if run_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    if run_to_update.status != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run already finished")

    # 2. Değişiklikleri yap
    run_to_update.exit_code = payload.exit_code
    run_to_update.ended_at = datetime.now(timezone.utc)
    run_to_update.status = "completed" if payload.exit_code == 0 else "failed"

    # 3. İstatistikleri hesapla (bu fonksiyon KENDİ sorgularını yapar)
    #    Bir önceki adımda bu fonksiyondaki NumPy hatalarını düzeltmiştik.
    stats = compute_and_store_run_stats(db, run_to_update)

    # 4. Veritabanına işle (commit)
    db.commit()
    # --- DÜZELTME BÖLÜM 1 BİTTİ ---


    # --- DÜZELTME BÖLÜM 2: YANITI HAZIRLA ---
    # 'response_model=schemas.RunDetail' için verinin tam (JOIN'lenmiş)
    # haline ihtiyacımız var. Veritabanından (artık kilitli değil)
    # güncellenmiş veriyi 'get_run' fonksiyonundaki gibi çekelim.
    
    run_with_details = (
        db.query(models.TestRun)
        .options(joinedload(models.TestRun.stats), joinedload(models.TestRun.samples))
        .filter(models.TestRun.id == run_id)
        .one_or_none()
    )
    
    if run_with_details is None:
         # Bu olmamalı, az önce güncelledik, ama bir güvenlik kontrolü
         raise HTTPException(status_code=404, detail="Run disappeared after update")

    # 'stats_override'a gerek yok, çünkü 'run_with_details' 
    # 'joinedload(models.TestRun.stats)' ile zaten güncel 'stats'ı çekti.
    return map_run_detail(run_with_details)


def compute_and_store_run_stats(db: Session, run: models.TestRun) -> models.RunStats | None:
    samples = (
        db.query(models.MetricSample)
        .filter(models.MetricSample.run_id == run.id)
        .order_by(models.MetricSample.ts.asc())
        .all()
    )
    if not samples:
        existing = db.query(models.RunStats).filter(models.RunStats.run_id == run.id).first()
        if existing:
            db.delete(existing)
        return None

    # --- BAŞLANGIÇ: YENİ GÜVENLİ KOD (None filtreleme) ---
    # None değerleri numpy'a gitmeden önce filtrele
    cpu_samples = [s.cpu_percent for s in samples if s.cpu_percent is not None]
    rss_samples = [s.rss_mb for s in samples if s.rss_mb is not None]

    # Eğer (filtrelenmiş) geçerli veri kalmadıysa, istatistik hesaplama
    if not cpu_samples or not rss_samples:
        existing = db.query(models.RunStats).filter(models.RunStats.run_id == run.id).first()
        if existing:
            db.delete(existing)
        return None

    # Artık güvenli olan (None içermeyen) listelerle numpy dizilerini oluştur
    cpu_values = np.array(cpu_samples, dtype=float)
    rss_values = np.array(rss_samples, dtype=float)
    # --- BİTİŞ: YENİ GÜVENLİ KOD ---

    avg_cpu = float(cpu_values.mean())
    p95_cpu = float(np.percentile(cpu_values, 95))
    max_cpu = float(cpu_values.max())

    avg_rss = float(rss_values.mean())
    p95_rss = float(np.percentile(rss_values, 95))

    duration_s = None
    if run.ended_at:
        duration_s = max((run.ended_at - run.started_at).total_seconds(), 0.0)

    stats = db.query(models.RunStats).filter(models.RunStats.run_id == run.id).first()
    if stats is None:
        stats = models.RunStats(run_id=run.id)
        db.add(stats)

    stats.avg_cpu = avg_cpu
    stats.p95_cpu = p95_cpu
    stats.max_cpu = max_cpu
    stats.avg_rss_mb = avg_rss
    stats.p95_rss_mb = p95_rss
    stats.duration_s = duration_s

    db.flush()
    return stats

def map_run_summary(run: models.TestRun) -> schemas.RunSummary:
    stats = map_stats(run)
    return schemas.RunSummary(
        id=run.id,
        command=run.command,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=run.status,
        exit_code=run.exit_code,
        baseline_run_id=run.baseline_run_id,
        stats=stats,
    )


def map_run_detail(run: models.TestRun, stats_override: models.RunStats | None = None) -> schemas.RunDetail:
    stats = map_stats(run, override=stats_override)
    stats = enrich_stats_with_samples(run, stats)
    return schemas.RunDetail(
        id=run.id,
        command=run.command,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=run.status,
        exit_code=run.exit_code,
        baseline_run_id=run.baseline_run_id,
        stats=stats,
    )


def map_stats(run: models.TestRun, override: models.RunStats | None = None) -> schemas.RunStats | None:
    stats_model = override or run.stats
    if not stats_model:
        return None
    stats = schemas.RunStats(
        run_id=stats_model.run_id,
        avg_cpu=stats_model.avg_cpu,
        p95_cpu=stats_model.p95_cpu,
        max_cpu=stats_model.max_cpu,
        avg_rss_mb=stats_model.avg_rss_mb,
        p95_rss_mb=stats_model.p95_rss_mb,
        duration_s=stats_model.duration_s,
        max_rss_mb=None,
    )
    return stats


def enrich_stats_with_samples(run: models.TestRun, stats: schemas.RunStats | None) -> schemas.RunStats | None:
    samples = getattr(run, "samples", None)
    if not samples:
        return stats

    max_cpu = max(sample.cpu_percent for sample in samples)
    max_rss = max(sample.rss_mb for sample in samples)

    if stats is None:
        stats = schemas.RunStats(
            run_id=run.id,
            avg_cpu=None,
            p95_cpu=None,
            max_cpu=float(max_cpu),
            avg_rss_mb=None,
            p95_rss_mb=None,
            duration_s=None,
            max_rss_mb=float(max_rss),
        )
    else:
        if stats.max_cpu is None:
            stats.max_cpu = float(max_cpu)
        if max_rss is not None:
            stats.max_rss_mb = float(max_rss)
    return stats
