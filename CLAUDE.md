# Plataforma de Telemetria OBD-II Simulada

Software que simula um veículo e faz telemetria OBD-II. Sem hardware. Spec em `docs/spec.md`.

## Como trabalhar (economia de tokens)

- Uma tarefa de `tasks/` por sessão. Use `/clear` entre sessões.
- Leia só o arquivo da tarefa e as seções de `docs/spec/` listadas no campo `spec` dela. Não leia a spec inteira.
- Modelo: o do campo `model` da tarefa. Suba um nível só se o campo `escalate_if` ocorrer.
- Testes primeiro. Mostre só falhas, não a saída completa.
- Peça diffs, não arquivos inteiros. Buscas amplas vão para subagente.
- Ordem e modelos: `docs/PLAN.md`. Para replanejar: skill `plan-sessions`.

## Comandos

```bash
pip install -e ".[dev]"
make test      # pytest -q --tb=short
make cov       # cobertura
make lint      # ruff + mypy
make run       # sobe servidor, simulador e coletor
```

## Convenções

- Python 3.12+, tipagem completa, `ruff` e `mypy` limpos.
- Código do protocolo é puro (sem I/O e sem `time.time()`); relógio injetável.
- Tudo determinístico com sementes. Nada de `random` global.
- Dublês de teste em `tests/fakes.py`.
- Layout `src/obd/{protocol,transport,simulator,collector,server,web}`.
- Texto do TCC: "software-in-the-loop", nunca "hardware-in-the-loop"; sem afirmar nada sobre veículo real.

## Git

- Nunca commitar em `main`; use um branch por tarefa (`task/NN-nome`).
- Commits curtos e no imperativo.

## Execução noturna

`python scripts/run_night.py` roda todas as tarefas em ordem, sem aprovação (ver docs/PLAN.md). Logs em `runs-night/`.
