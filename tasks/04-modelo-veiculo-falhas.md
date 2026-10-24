---
id: "04"
title: Modelo de veículo, perfis de condução e falhas
model: sonnet
session: 5
order: 5
depends_on: ["03"]
parallel_with: ["06"]
weight: M
escalate_if: "o modelo não é determinístico com as mesmas sementes após 2 iterações"
spec: docs/spec/06-simulador.md
---

## Escopo

Trocar o dublê da ECU por um modelo físico real e implementar o catálogo de falhas.

## Arquivos

- `simulator/vehicle_model.py`: modelo com passo de 10 ms, todas as variáveis da tabela da spec, ruído gaussiano com semente e `set_override`.
- `config/profiles/*.yaml`: `parado`, `urbano`, `rodovia`, `ciclo_120s`, `esforco`.
- `simulator/faults.py`: `FaultInjector` com DTC armazenado e pendente, atraso, perda de quadros, corrupção, ECU muda, PID não suportado, resposta negativa e atraso de ISO-TP.
- Integração na ECU (`simulator/ecu.py`): freeze frame (Modo 02) capturado quando um DTC é injetado e Modo 04 limpando DTCs e freeze frame.

## Testes (escrever primeiro)

- Determinismo: duas execuções com as mesmas sementes e o mesmo perfil geram a mesma sequência de estados.
- MAP nunca excede a pressão atmosférica (motor aspirado).
- Temperatura do líquido tende a 90 °C com a constante de tempo configurada.
- Rotação segue a fórmula com marcha, relação final e raio do pneu.
- DTC injetado aparece no Modo 03 e acende o MIL no PID 0x01; Modo 04 zera.
- Perda e corrupção de quadros ocorrem com a probabilidade configurada (tolerância estatística com semente fixa).
- Freeze frame guarda os valores do instante da falha.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration
make lint
```

Cobre RF03, RF04 e RF11 (lado do simulador).

## Fora desta tarefa

API de controle e painel (tarefa 08) e servidor ELM327 (tarefa 09).

## Prompt de lançamento

```text
Leia apenas tasks/04-modelo-veiculo-falhas.md e docs/spec/06-simulador.md. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
