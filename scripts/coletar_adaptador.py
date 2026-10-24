"""Coleta de um adaptador ELM327 remoto (ex.: o ESP32) com o mesmo coletor do simulador.

Uso (veja docs/hardware/manual-montagem.md):

    python scripts/coletar_adaptador.py --host 192.168.0.10 --port 35000 --ciclos 20
    python scripts/coletar_adaptador.py --host 192.168.0.10 --servidor-url http://localhost:8000

Sem `--servidor-url`, só imprime. Com ele, publica no servidor (suba antes com `make run`
ou `docker compose up`) e o dashboard mostra os dados do adaptador.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from obd.collector.collector import Collector
from obd.collector.factory import build_transport
from obd.collector.publisher import HttpPublisher, Publisher, RecordingPublisher
from obd.collector.scheduler import CollectorConfig
from obd.protocol.schemas import Sample


def _linha(s: Sample) -> str:
    vals = " ".join(f"{v.pid}={v.value:g}{v.unit}" for v in s.values.values())
    e = s.errors
    cab = f"seq={s.seq} ciclo={s.cycle_ms:.0f}ms"
    return f"{cab} erros(timeout={e.timeouts},invalido={e.invalid}) {vals}"


async def _main(args: argparse.Namespace) -> int:
    cfg = CollectorConfig.from_yaml()
    transport = build_transport(
        "elm327_tcp", host=args.host, port=args.port, search_timeout_s=cfg.search_timeout_s
    )
    publisher: Publisher = (
        HttpPublisher(args.servidor_url) if args.servidor_url else RecordingPublisher()
    )
    coletor = Collector(
        transport, publisher, rates=cfg.plan, timeout_ms=args.timeout_ms, source="elm327_tcp"
    )
    try:
        await coletor.start()
    except OSError as exc:
        print(f"ERRO: não conectou em {args.host}:{args.port}: {exc!r}", file=sys.stderr)
        return 2
    if not coletor.supported:
        print("ERRO: o adaptador não anunciou nenhum PID (descoberta falhou).", file=sys.stderr)
        await coletor.close()
        return 1
    print(f"PIDs suportados: {sorted(f'0x{p:02X}' for p in coletor.supported)}")
    try:
        for _ in range(args.ciclos):
            print(_linha(await coletor.run_cycle()))
            await asyncio.sleep(args.intervalo_ms / 1000)
    finally:
        await coletor.close()
    for ev in coletor.events:
        print(f"evento {ev.kind}: {ev.detail}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=35000)
    ap.add_argument("--ciclos", type=int, default=20)
    ap.add_argument("--intervalo-ms", type=int, default=200)
    ap.add_argument("--timeout-ms", type=int, default=500)
    ap.add_argument("--servidor-url", help="ex.: http://localhost:8000 (opcional)")
    return asyncio.run(_main(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
