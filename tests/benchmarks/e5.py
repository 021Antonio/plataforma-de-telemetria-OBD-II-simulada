"""E5: VIN por ISO-TP com STmin de 0, 1 e 10 ms (tempo de remontagem)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from obd.protocol.services import MODE_VEHICLE_INFO, PID_VIN
from obd.simulator.control_api import Simulator
from obd.simulator.ecu import DEFAULT_VIN
from obd.transport.loopback import LoopbackTransport

from . import plots
from .runner import (
    RunOutput,
    Scenario,
    default_out_dir,
    parse_args,
    print_table,
    write_outputs,
)
from .stats import summarize

NAME = "E5"
REPETITIONS = 100  # a spec não fixa o número de repetições
STMINS_MS = (0, 1, 10)
VIN_REQUEST = bytes([MODE_VEHICLE_INFO, PID_VIN])


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    reps = REPETITIONS if duration is None else max(1, int(duration))  # --duration = repetições
    results: list[RunOutput] = []
    csv_rows: list[dict[str, Any]] = []
    for stmin in STMINS_MS:
        sim = Simulator(time.monotonic)
        transport = LoopbackTransport(sim.ecu, clock=time.monotonic, stmin=stmin)
        times: list[float] = []
        wrong = 0
        for i in range(reps):
            t0 = time.perf_counter()
            resp = await transport.request(VIN_REQUEST, timeout_ms=1000)
            ms = (time.perf_counter() - t0) * 1000
            ok = resp is not None and resp.endswith(DEFAULT_VIN.encode("ascii"))
            wrong += 0 if ok else 1
            times.append(ms)
            csv_rows.append(
                {
                    "run": f"stmin{stmin}",
                    "stmin_ms": stmin,
                    "rep": i,
                    "remontagem_ms": ms,
                    "vin_ok": ok,
                }
            )
        metrics = {"remontagem_ms": summarize(times).as_dict(), "vin_incorreto": wrong}
        results.append(
            RunOutput(
                Scenario(label=f"stmin{stmin}", duration_s=0.0), [], metrics, {"stmin_ms": stmin}
            )
        )
    doc = write_outputs(
        NAME,
        out_dir,
        results,
        config={"stmin_ms": list(STMINS_MS), "repeticoes": reps},
        csv_rows=csv_rows,
    )
    if plot:
        plots.plot_e5(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(
        asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    )


if __name__ == "__main__":
    main()
