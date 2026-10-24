---
id: "03"
title: Transporte plugável e ECU virtual
model: sonnet
session: 4
order: 4
depends_on: ["01", "02"]
parallel_with: ["06"]
weight: M
escalate_if: "a ECU não responde corretamente ao ISO-TP ou há condição de corrida após 2 iterações"
spec: docs/spec/03-modulos-interfaces.md, docs/spec/04-protocolo.md, docs/spec/06-simulador.md
---

## Escopo

Criar a interface `Transport`, duas implementações e a ECU virtual que responde à ISO 15765-4. O modelo de veículo ainda é um dublê.

## Arquivos

- `transport/base.py`: `Transport` (Protocol) com `open`, `close`, `request(payload, timeout_ms)` e `name`.
- `transport/loopback.py`: `LoopbackTransport` ligado direto a uma ECU em memória (para testes).
- `transport/can_virtual.py`: usa `python-can` com `interface="virtual"`, envia em 0x7DF e escuta 0x7E8, remonta ISO-TP e devolve os bytes.
- `simulator/ecu.py`: nó que escuta 0x7DF e 0x7E0, responde em 0x7E8 aos Modos 01, 02, 03, 04, 07 e 09, usa as fórmulas de `protocol`, devolve PIDs não suportados como silêncio, aplica atraso configurável e registra `(request_id, true_value)` para cada resposta.
- Dublês em `tests/fakes.py`: `FakeClock`, `FakeVehicleModel` (valores constantes ou em rampa), `ScriptedTransport`.

## Testes (escrever primeiro)

- Integração com `LoopbackTransport`: lê os 10 PIDs e confere contra o `FakeVehicleModel`, com erro dentro de `resolution / 2`.
- Integração com `can_virtual`: o mesmo teste por barramento CAN virtual.
- Descoberta de PIDs: a máscara de 0x00, 0x20 e 0x40 corresponde aos PIDs configurados (RF02).
- VIN por ISO-TP completo.
- Timeout quando o PID não é suportado.
- Atraso de resposta com `FakeClock`: a resposta chega depois do atraso configurado.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration
make lint
```

Cobre RF01, RF02, RF05 e parte de RF03, RF04 e RF12.

## Fora desta tarefa

Modelo físico de veículo, perfis e catálogo completo de falhas (tarefa 04).

## Prompt de lançamento

```text
Leia apenas tasks/03-transporte-ecu.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
