from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.sql import func

from .db import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    command = Column(Text, nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="running")
    exit_code = Column(Integer, nullable=True)
    baseline_run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True)

    baseline_run = relationship("TestRun", remote_side=[id], uselist=False)
    samples = relationship(
        "MetricSample",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stats = relationship(
        "RunStats",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MetricSample(Base):
    __tablename__ = "metric_samples"

    id = Column(BigInteger, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    cpu_percent = Column(Float, nullable=False)
    rss_mb = Column(Float, nullable=False)

    run = relationship("TestRun", back_populates="samples")


class RunStats(Base):
    __tablename__ = "run_stats"

    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), primary_key=True)
    avg_cpu = Column(Float, nullable=True)
    p95_cpu = Column(Float, nullable=True)
    max_cpu = Column(Float, nullable=True)
    avg_rss_mb = Column(Float, nullable=True)
    p95_rss_mb = Column(Float, nullable=True)
    duration_s = Column(Float, nullable=True)

    run = relationship("TestRun", back_populates="stats")
