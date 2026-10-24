"""Executa o roteiro contra um endereço TCP e compara com as respostas esperadas."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .roteiro import ROTEIRO

DOURADO = Path(__file__).with_name("dourado.json")
PROMPT_FIM = "\r\r>"


@dataclass(frozen=True)
class Resultado:
    indice: int
    comando: str
    esperado: str | None  # None = ignorado pelo perfil
    obtido: str

    @property
    def ok(self) -> bool:
        return self.esperado is None or self.esperado == self.obtido


def carregar_dourado(caminho: Path = DOURADO) -> list[dict[str, str]]:
    dados: list[dict[str, str]] = json.loads(caminho.read_text(encoding="utf-8"))
    if [d["comando"] for d in dados] != [p.comando for p in ROTEIRO]:
        raise ValueError(
            f"{caminho} não corresponde ao roteiro; regenere com tests.conformance.gerar"
        )
    return dados


def carregar_perfil(caminho: Path | None) -> dict[str, Any]:
    """Perfil opcional: `ignorar` (lista de comandos) e `esperado` (comando -> resposta crua)."""
    if caminho is None:
        return {}
    perfil: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
    return perfil


async def _enviar(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, comando: str, timeout: float
) -> str:
    writer.write(comando.encode() + b"\r")
    await writer.drain()
    bruto = await asyncio.wait_for(reader.readuntil(b">"), timeout)
    return bruto.decode("latin-1")


async def capturar(host: str, port: int, *, timeout: float = 2.0) -> list[str]:
    """Respostas cruas (com o prompt final) de cada passo do roteiro."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        return [await _enviar(reader, writer, p.comando, timeout) for p in ROTEIRO]
    finally:
        writer.close()
        await writer.wait_closed()


def comparar(
    obtidas: Sequence[str],
    dourado: Sequence[Mapping[str, str]],
    perfil: Mapping[str, Any] | None = None,
) -> list[Resultado]:
    perfil = perfil or {}
    ignorar = set(perfil.get("ignorar", []))
    trocas: Mapping[str, str] = perfil.get("esperado", {})
    saida = []
    for i, (passo, d, obtido) in enumerate(zip(ROTEIRO, dourado, obtidas, strict=True)):
        esperado: str | None = trocas.get(passo.comando, d["resposta"])
        if passo.comando in ignorar:
            esperado = None
        saida.append(Resultado(i, passo.comando, esperado, obtido))
    return saida


async def executar(
    host: str,
    port: int,
    *,
    dourado: Sequence[Mapping[str, str]] | None = None,
    perfil: Mapping[str, Any] | None = None,
    timeout: float = 2.0,
) -> list[Resultado]:
    esperado = carregar_dourado() if dourado is None else dourado
    return comparar(await capturar(host, port, timeout=timeout), esperado, perfil)
