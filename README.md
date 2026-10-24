# Plataforma de Telemetria OBD-II Simulada

Software que simula um veículo e faz telemetria OBD-II, sem hardware. O coletor
fala apenas com a interface `Transport`, então o simulador pode ser trocado por
um adaptador real no futuro sem mudar o coletor.

A especificação completa está em [docs/spec.md](docs/spec.md).

## Instalação

Requer Python 3.12 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Testes e qualidade

```bash
make test   # testes
make cov    # testes com cobertura
make lint   # ruff e mypy
```

## Execução

`make run` ainda não sobe nada: o servidor, o simulador e o coletor entram em
tarefas posteriores.
