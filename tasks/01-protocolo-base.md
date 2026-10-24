---
id: "01"
title: Núcleo de protocolo (PIDs, DTCs, quadros, serviços e schemas)
model: sonnet
session: 2
order: 2
depends_on: ["00"]
parallel_with: []
weight: M
escalate_if: "testes de propriedade ou de fórmulas seguem falhando após 2 iterações"
spec: docs/spec/03-modulos-interfaces.md, docs/spec/04-protocolo.md
---

## Escopo

Implementar `src/obd/protocol/` sem I/O: tudo puro e testável sem rede. Sem ISO-TP (tarefa 02).

## Arquivos

- `pids.py`: `PidDef` e a tabela dos PIDs da seção 4 da spec, com `encode` e `decode`, máscara de PIDs suportados (0x00, 0x20, 0x40) e decodificação do PID 0x01 (MIL e contagem).
- `dtc.py`: bytes para código (`03 00` para `P0300`) e vice-versa, e descrições mínimas (P0300 a P0304, P0171, P0172, P0420, P0133).
- `frames.py`: monta quadros CAN de 8 bytes (preenchimento `0x55`), valida DLC e identificadores 0x7DF, 0x7E0 a 0x7E7 e 0x7E8, e calcula o tempo de quadro `C = 47 + 8s + floor((34 + 8s - 1)/4)`.
- `services.py`: `build_request(mode, pid)`, `parse_response(raw)` para os Modos 01, 03, 04 e 07 em quadro único e resposta negativa `7F`.
- `schemas.py`: modelos Pydantic `Sample`, `DtcReport` e `Stats`, conforme `docs/spec/05-api.md`.

## Testes (escrever primeiro)

- `tests/unit/protocol/test_pids.py`: vetores conhecidos, por exemplo `0C` com `1F 40` igual a 2000 rpm e `05` com `7B` igual a 83 °C.
- Propriedade com `hypothesis`: `decode(encode(x))` dentro de `resolution / 2` para 1.001 valores igualmente espaçados em cada PID.
- `test_dtc.py`: ida e volta para todos os sistemas (P, C, B, U).
- `test_frames.py`: preenchimento, DLC inválido e C = 135 bits para 8 bytes.
- `test_services.py`: resposta com modo + 0x40 e PID repetido; resposta com PID errado é rejeitada; `7F` é interpretada.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit/protocol
pytest --cov=src/obd/protocol --cov-fail-under=80 tests/unit/protocol
make lint
```

Cobre RF06 (decodificação) e RNF06 (cobertura).

## Fora desta tarefa

ISO-TP, Modos 02 e 09, transporte e simulador.

## Prompt de lançamento

```text
Leia apenas tasks/01-protocolo-base.md e as seções de docs/spec citadas nele. Escreva os testes primeiro, implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
