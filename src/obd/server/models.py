"""Esquema SQLite do servidor (docs/spec/07-dados-web.md)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

runs = Table(
    "runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("started_at", Float, nullable=False),
    Column("source", String, nullable=False),
    Column("seed_model", Integer),
    Column("seed_ecu", Integer),
    Column("profile", String),
    Column("notes", String),
)

samples = Table(
    "samples",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("runs.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("ts_pub", Float, nullable=False),
    Column("ts_recv", Float, nullable=False),
    Column("latency_ms", Float, nullable=False),
    Column("cycle_ms", Float, nullable=False),
    Column("source", String, nullable=False),
    Column("timeouts", Integer, nullable=False),
    Column("invalid", Integer, nullable=False),
    UniqueConstraint("run_id", "seq", name="uq_samples_run_seq"),
    Index("ix_samples_ts_pub", "ts_pub"),
)

readings = Table(
    "readings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sample_id", Integer, ForeignKey("samples.id"), nullable=False),
    Column("pid", String, nullable=False),
    Column("name", String, nullable=False),
    Column("value", Float, nullable=False),
    Column("unit", String, nullable=False),
    Column("rtt_ms", Float, nullable=False),
    Column("true_value", Float),  # só preenchido pelo executor de ensaios
    Index("ix_readings_sample_pid", "sample_id", "pid"),
)

# Uma linha por código; relatório sem DTCs vira uma linha com `code` NULL.
dtc_events = Table(
    "dtc_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("runs.id"), nullable=False),
    Column("report_id", Integer, nullable=False),
    Column("ts_recv", Float, nullable=False),
    Column("ts", Float, nullable=False),
    Column("mil", Boolean, nullable=False),
    Column("count", Integer, nullable=False),
    Column("code", String),
    Column("description", String),
    Column("status", String),
    Index("ix_dtc_events_report", "report_id"),
)

comm_events = Table(
    "comm_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("runs.id"), nullable=False),
    Column("ts", Float, nullable=False),
    Column("kind", String, nullable=False),
    Column("detail", String, nullable=False),
    Index("ix_comm_events_run_kind", "run_id", "kind"),
)
