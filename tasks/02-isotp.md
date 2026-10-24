---
id: "02"
title: ISO-TP completo e Modos 02 e 09
model: sonnet
session: 3
order: 3
depends_on: ["01"]
parallel_with: []
weight: M
escalate_if: "remontagem multiquadro falha em algum comprimento após 2 iterações"
spec: docs/spec/04-protocolo.md
---

## Escopo

Implementar o transporte ISO-TP (ISO 15765-2) em `src/obd/protocol/isotp.py` e os serviços que dependem dele.

## Arquivos

- `isotp.py`:
  - segmentação de uma mensagem em SF, ou FF seguido de CFs;
  - remontagem com validação de sequência (0 a F, com volta) e de comprimento total (12 bits);
  - quadros de controle de fluxo (`30 BS STmin`);
  - tratamento de `STmin` e `BS` do lado emissor;
  - estouro de N_Cr (1 s) aborta a recepção.
- `services.py` (acrescentar): Modo 02 (`02 PID 00` para `42 PID 00 dados`) e Modo 09 PID 0x02 (VIN, `49 02 01` mais 17 bytes).
- A API deve ser pura: funções que recebem e devolvem bytes e estados. O tempo entra por parâmetro (relógio injetável), nunca por `time.time()`.

## Testes (escrever primeiro)

- Propriedade com `hypothesis`: segmentar e remontar qualquer mensagem de 8 a 4095 bytes devolve a original.
- Sequência de CF fora de ordem é rejeitada; CF repetido é rejeitado.
- VIN de 17 caracteres atravessa FF, FC e CFs corretamente.
- `STmin` de 0, 1 e 10 ms é respeitado pelo emissor (com relógio falso).
- Estouro de N_Cr devolve erro de timeout.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit/protocol
pytest --cov=src/obd/protocol --cov-fail-under=80 tests/unit/protocol
make lint
```

Cobre RF05 e parte de RF04.

## Fora desta tarefa

Transporte sobre barramento e ECU virtual (tarefa 03).

## Prompt de lançamento

```text
Leia apenas tasks/02-isotp.md e docs/spec/04-protocolo.md. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
