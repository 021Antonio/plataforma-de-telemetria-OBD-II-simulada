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

## Como rodar

```bash
make run     # servidor, simulador, painel, ELM327 e coletor num só processo
```

- Dashboard: <http://localhost:8000/>
- Painel de controle do simulador: <http://localhost:8001/>
- Servidor ELM327 (TCP): `localhost:35000`

Ctrl+C encerra tudo. Opções: `python -m obd run --perfil urbano --db data/obd.db --sem-elm327`
(portas com `--porta-servidor`, `--porta-painel` e `--porta-elm327`).

> **Atenção:** abra os HTML sempre pelas URLs acima. Abri-los por servidor estático
> (Live Server, `file://`) mostra a tela sem dados, porque a API e o WebSocket só existem
> no servidor da plataforma.

Com Docker: `docker compose up app` (o Mosquitto continua opcional: `--profile mqtt`).
