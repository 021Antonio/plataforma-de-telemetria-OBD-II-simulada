"""Gráficos dos ensaios com matplotlib (backend sem janela), lidos de `<ensaio>.csv/.json`."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _load(out_dir: Path, stem: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    csv_path = out_dir / f"{stem}.csv"
    rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    doc: dict[str, Any] = json.loads((out_dir / f"{stem}.json").read_text(encoding="utf-8"))
    return rows, doc


def _save(fig: Any, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_true_vs_decoded(rows: list[dict[str, str]], path: Path, *, max_points: int = 300) -> Path:
    """Valor real (linha) contra o decodificado (pontos), um quadro por PID."""
    names = sorted({r["name"] for r in rows})
    cols = 2
    fig, axes = plt.subplots(
        (len(names) + 1) // cols, cols, figsize=(11, 2.2 * ((len(names) + 1) // cols))
    )
    for ax, name in zip(axes.flat, names, strict=False):
        sel = [r for r in rows if r["name"] == name][:max_points]
        seq = [int(r["seq"]) for r in sel]
        ax.plot(seq, [float(r["true_value"]) for r in sel], lw=1.2, label="real")
        ax.plot(seq, [float(r["value"]) for r in sel], ".", ms=3, label="decodificado")
        ax.set_title(f"{name} ({sel[0]['unit']})", fontsize=9)
        ax.set_xlabel("seq", fontsize=8)
    axes.flat[0].legend(fontsize=8)
    for ax in list(axes.flat)[len(names) :]:
        ax.axis("off")
    return _save(fig, path)


def plot_rtt_distribution(rows: list[dict[str, str]], path: Path) -> Path:
    rtt = [float(r["rtt_ms"]) for r in rows]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(rtt, bins=40)
    ax.axvline(50, color="tab:red", ls="--", label="P2 = 50 ms")
    ax.set_xlabel("RTT por PID (ms)")
    ax.set_ylabel("leituras")
    ax.legend()
    return _save(fig, path)


def plot_e1(out_dir: Path) -> list[Path]:
    rows, _ = _load(out_dir, "e1")
    return [
        plot_true_vs_decoded(rows, out_dir / "e1_real_vs_decodificado.png"),
        plot_rtt_distribution(rows, out_dir / "e1_rtt.png"),
    ]


def _line(
    out_dir: Path,
    stem: str,
    xs: list[float],
    series: dict[str, list[float]],
    xlabel: str,
    title: str,
) -> Path:
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for label, ys in series.items():
        ax.plot(xs, ys, "o-", label=label)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)
    ax.legend()
    return _save(fig, out_dir / f"{stem}.png")


def plot_e2(out_dir: Path) -> list[Path]:
    """Sensibilidade: ciclo e taxa em função do atraso da ECU."""
    _, doc = _load(out_dir, "e2")
    runs = doc["runs"]
    delays = [float(r["config"]["delay_ms"][0]) for r in runs]
    return [
        _line(
            out_dir,
            "e2_sensibilidade",
            delays,
            {
                "ciclo médio (ms)": [r["metrics"]["ciclo_ms"]["mean"] for r in runs],
                "ciclo p95 (ms)": [r["metrics"]["ciclo_ms"]["p95"] for r in runs],
            },
            "atraso da ECU (ms)",
            "E2: ciclo em função do atraso",
        ),
        _line(
            out_dir,
            "e2_taxa",
            delays,
            {"ciclos/s": [r["metrics"]["ciclos_por_s"] for r in runs]},
            "atraso da ECU (ms)",
            "E2: taxa de ciclos",
        ),
    ]


def plot_e3(out_dir: Path) -> list[Path]:
    """Escalabilidade: taxa por PID e leituras por segundo em função do número de PIDs."""
    _, doc = _load(out_dir, "e3")
    runs = doc["runs"]
    n = [float(len(r["config"]["pids"])) for r in runs]
    return [
        _line(
            out_dir,
            "e3_escalabilidade",
            n,
            {
                "leituras/s": [r["metrics"]["leituras_por_s"] for r in runs],
                "taxa por PID (Hz)": [
                    sum(p["taxa_hz"] for p in r["metrics"]["por_pid"].values())
                    / len(r["config"]["pids"])
                    for r in runs
                ],
            },
            "PIDs lidos",
            "E3: escalabilidade",
        )
    ]


def plot_e4(out_dir: Path) -> list[Path]:
    _, doc = _load(out_dir, "e4")
    runs = doc["runs"]
    loss = [100 * float(r["config"]["frame_loss"]) for r in runs]
    return [
        _line(
            out_dir,
            "e4_perdas",
            loss,
            {
                "timeouts": [float(r["metrics"]["timeouts"]) for r in runs],
                "leituras/s": [r["metrics"]["leituras_por_s"] for r in runs],
            },
            "perda de quadros (%)",
            "E4: efeito da perda de quadros",
        )
    ]


def plot_e5(out_dir: Path) -> list[Path]:
    _, doc = _load(out_dir, "e5")
    runs = doc["runs"]
    return [
        _line(
            out_dir,
            "e5_stmin",
            [float(r["stmin_ms"]) for r in runs],
            {
                "média (ms)": [r["metrics"]["remontagem_ms"]["mean"] for r in runs],
                "p95 (ms)": [r["metrics"]["remontagem_ms"]["p95"] for r in runs],
            },
            "STmin (ms)",
            "E5: remontagem do VIN",
        )
    ]


def plot_e7(out_dir: Path) -> list[Path]:
    _, doc = _load(out_dir, "e7")
    runs = doc["runs"]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    labels = [r["label"] for r in runs]
    ax.bar(labels, [r["metrics"]["latencia_ms"]["mean"] for r in runs], label="média")
    ax.bar(labels, [r["metrics"]["latencia_ms"]["p95"] for r in runs], width=0.4, label="p95")
    ax.set_ylabel("latência coletor→banco (ms)")
    ax.legend()
    return [_save(fig, out_dir / "e7_latencia.png")]
