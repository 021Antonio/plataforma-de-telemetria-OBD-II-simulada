---
id: "10"
title: Ensaios E1 a E7, métricas e gráficos
model: sonnet
session: 12
order: 12
depends_on: ["04", "05", "06", "09", "12"]
parallel_with: []
weight: M
escalate_if: "métricas inconsistentes entre execuções com as mesmas sementes após 2 iterações"
spec: docs/spec/08-testes.md
---

## Escopo

Automatizar os ensaios de desempenho e gerar CSV, JSON, estatísticas e gráficos.

## Arquivos

- `tests/benchmarks/runner.py`: sobe simulador, coletor e servidor em processos, aplica o cenário, junta o `true_value` da ECU ao `Sample` por `seq` e grava em `readings.true_value`.
- `tests/benchmarks/e1.py` a `e7.py`: cenários da tabela de ensaios da spec. O E7 compara HTTP e MQTT (latência e perdas).
- `tests/benchmarks/stats.py`: média, desvio padrão, mediana, p95, p99 e máximo.
- `tests/benchmarks/plots.py`: gráficos com `matplotlib` (valores reais contra decodificados, distribuição de RTT, sensibilidade, escalabilidade).
- Saída em `runs/<data>/` com CSV, JSON, sementes e configuração. `runs/` fica no `.gitignore`, com exceção de um exemplo versionado em `docs/ensaios/`.
- `docs/ensaios.md`: tabela de resultados e instruções para repetir em uma segunda máquina.

## Testes (escrever primeiro)

- `stats.py` com vetores conhecidos.
- Um ensaio curto (10 s) roda de ponta a ponta e produz CSV válido.
- Mesmas sementes geram a mesma sequência de valores reais.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/benchmarks -k "stats or smoke"
python -m tests.benchmarks.e1 --duration 240
```

- RNF01 a RNF04 medidos e registrados.
- Erro de decodificação menor ou igual a metade da resolução em 100% das leituras.
- Perdas, duplicações e estouros de tempo iguais a zero em E1.

## Fora desta tarefa

Redação do texto do TCC (tarefa 11).

## Prompt de lançamento

```text
Leia apenas tasks/10-ensaios.md e docs/spec/08-testes.md. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas e a tabela final de métricas.
```
