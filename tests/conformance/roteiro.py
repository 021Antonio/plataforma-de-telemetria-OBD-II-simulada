"""Roteiro de conformidade: os 19 comandos do E6 mais os casos da tarefa 16, como dados.

Cada passo traz o comando, o estado da sessão esperado depois dele (eco, avanço de linha,
espaços, cabeçalhos) e a chave para achar a resposta esperada em `dourado.json`. A resposta
esperada não fica aqui: vem do simulador com valores fixos (ver `gerar.py`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Estado:
    eco: bool = True
    avanco_linha: bool = False
    espacos: bool = True
    cabecalhos: bool = False


@dataclass(frozen=True)
class Passo:
    comando: str
    estado: Estado  # estado da sessão depois do comando
    nota: str = ""


_E0 = Estado(eco=False)
_L0 = _E0
_H1 = Estado(eco=False, cabecalhos=True)
_S0 = Estado(eco=False, espacos=False)


def _p(comando: str, estado: Estado, nota: str = "") -> Passo:
    return Passo(comando, estado, nota)


ROTEIRO: tuple[Passo, ...] = (
    # os 19 comandos do E6 (o eco liga após o ATZ, como no chip real)
    _p("ATZ", Estado(), "reinicia; não ecoa"),
    _p("ATE0", _E0),
    _p("ATL0", _L0),
    _p("ATS1", _E0),
    _p("ATH0", _E0),
    _p("ATSP0", _E0),
    _p("ATDP", _E0, "AUTO, protocolo"),
    _p("ATRV", _E0),
    _p("0100", _E0, "SEARCHING... só na primeira consulta"),
    _p("0120", _E0),
    _p("010C", _E0),
    _p("010D", _E0),
    _p("0105", _E0),
    _p("0111", _E0),
    _p("0101", _E0),
    _p("03", _E0, "sem DTCs: NO DATA"),
    _p("0902", _E0, "VIN multiquadro remontado"),
    _p("01FF", _E0, "PID sem suporte"),
    _p("XYZ", _E0, "comando desconhecido"),
    # casos da tarefa 16
    _p("0100", _E0, "sem SEARCHING... na segunda vez"),
    _p("ATDPN", _E0, "A6 após ATSP0"),
    _p("0900", _E0, "máscara do modo 09"),
    _p("0600", _E0, "serviço sem suporte: NO DATA"),
    _p("ATH1", _H1),
    _p("010C", _H1, "com cabeçalho"),
    _p("0900", _H1),
    _p("0902", _H1, "um quadro CAN por linha"),
    _p("ATH0", _E0),
    _p("ATS0", _S0),
    _p("010C", _S0, "sem espaços"),
    _p("0902", _S0),
    _p("ATS1", _E0),
    _p("ATL1", Estado(eco=False, avanco_linha=True)),
    _p("010C", Estado(eco=False, avanco_linha=True), "CR LF"),
    _p("ATL0", _E0),
    _p("ATE1", Estado(), "responde OK sem eco; o eco liga depois"),
    _p("010C", Estado(), "com eco"),
    _p("ATE0", _E0),
    _p("ATSP6", _E0),
    _p("ATDPN", _E0, "6 após ATSP6"),
    _p("ATDP", _E0, "sem AUTO"),
)
