"""Suíte de conformidade contra o `host_server` do firmware (biblioteca C++ + ECU de bancada)."""

from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from conformance.executor import executar

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware"

pytestmark = pytest.mark.skipif(
    shutil.which("g++") is None or shutil.which("make") is None, reason="sem g++/make"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def porta() -> Iterator[int]:
    subprocess.run(["make", "-C", str(FIRMWARE), "host_server"], check=True, capture_output=True)
    port = _free_port()
    proc = subprocess.Popen(
        [str(FIRMWARE / "build" / "host_server"), str(port)], stdout=subprocess.PIPE
    )
    assert proc.stdout is not None
    proc.stdout.readline()  # "ouvindo": o soquete já aceita conexões
    yield port
    proc.terminate()
    proc.wait(timeout=5)


def test_conformidade_sem_divergencias(porta: int) -> None:
    resultados = asyncio.run(executar("127.0.0.1", porta))
    assert [r for r in resultados if not r.ok] == []
    assert len(resultados) == 41
