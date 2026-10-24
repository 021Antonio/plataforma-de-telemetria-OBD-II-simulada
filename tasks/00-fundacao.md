---
id: "00"
title: Fundação do repositório
model: haiku
session: 1
order: 1
depends_on: []
parallel_with: []
weight: P
escalate_if: "make test ou make lint ainda falham após 2 iterações"
spec: docs/spec/02-arquitetura-stack.md
---

## Escopo

Criar o esqueleto do projeto, sem lógica de negócio.

## Arquivos

- `pyproject.toml` (nome `obd-telemetry`, Python >= 3.12, layout `src/`).
  - Dependências: `python-can`, `fastapi`, `uvicorn`, `sqlalchemy>=2`, `aiosqlite`, `pydantic>=2`, `pyyaml`, `httpx`.
  - Extras de desenvolvimento: `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`, `pandas`, `matplotlib`.
- `Makefile` com alvos `test`, `cov`, `lint`, `run`.
  - `test` roda `pytest -q --tb=short`.
- Pacotes vazios com `__init__.py` conforme `docs/spec/02-arquitetura-stack.md`: `src/obd/{protocol,transport,simulator,collector,server,web}`.
- `config/default.yaml` com portas (8000, 8001, 35000), taxa CAN (500000) e lista de PIDs.
- `tests/{unit,integration,e2e,benchmarks}/` e um teste de fumaça que importa `obd`.
- `.pre-commit-config.yaml` (ruff e mypy) e `.github/workflows/ci.yml` rodando `make lint` e `make test`.
- `README.md` curto: o que é, como instalar, como rodar os testes, link para `docs/spec.md`.

## Critério de pronto

```bash
pip install -e ".[dev]"
make lint    # passa
make test    # passa com o teste de fumaça
```

## Fora desta tarefa

Qualquer lógica de protocolo, simulador, coletor ou servidor.

## Prompt de lançamento

```text
Leia apenas tasks/00-fundacao.md e docs/spec/02-arquitetura-stack.md. Implemente a tarefa, rode make lint e make test e mostre só as falhas.
```
