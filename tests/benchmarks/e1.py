"""E1: 240 s, 10 PIDs, ECU em 10 ms ± 3 ms, falha P0300 aos 100 s."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import plots
from .runner import (
    Scenario,
    default_out_dir,
    parse_args,
    print_table,
    run_scenario,
    write_outputs,
)

NAME = "E1"
DURATION_S = 240.0
FAULT_CODE = "P0300"
FAULT_AT = 100 / 240  # fração da duração: 100 s em 240 s
SEED_MODEL = 1
SEED_ECU = 1


def scenario(duration: float) -> Scenario:
    return Scenario(
        label="run1",
        duration_s=duration,
        fault_code=FAULT_CODE,
        fault_at_s=duration * FAULT_AT,
        seed_model=SEED_MODEL,
        seed_ecu=SEED_ECU,
    )


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    sc = scenario(duration or DURATION_S)
    result = await run_scenario(sc, out_dir, db_name="e1_run1.db")
    doc = write_outputs(NAME, out_dir, [result], config={"duracao_s": sc.duration_s})
    if plot:
        plots.plot_e1(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    doc = asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    print_table(doc)


if __name__ == "__main__":
    main()
