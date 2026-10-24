---
id: "13"
title: Orquestração (make run), serviços no Compose e verificação de ponta a ponta
model: sonnet
session: 13
order: 13
depends_on: ["05", "06", "07", "08", "09", "12"]
parallel_with: []
weight: M
escalate_if: "o processo não sobe ou não encerra limpo após 2 iterações, ou a amostra não chega ao dashboard"
spec: docs/spec/02-arquitetura-stack.md, docs/spec/05-api.md, docs/spec/07-dados-web.md
---

## Escopo

Hoje cada peça existe e é testada, mas **nada sobe o sistema**: `make run` só imprime uma mensagem. Esta tarefa liga tudo e prova que o dado chega do simulador ao dashboard.

## Arquivos

- `src/obd/__main__.py` e `src/obd/runner.py`: `python -m obd run [--config config/default.yaml] [--perfil urbano] [--db data/obd.db] [--sem-elm327]`.
  Em um único processo `asyncio`, sobe:
  - servidor FastAPI (`create_app` com `SqlStorage` em arquivo) na porta `portas.servidor` (8000), servindo o dashboard em `/`;
  - painel de controle do simulador (`create_control_app`) na porta `portas.painel` (8001), servindo o painel em `/`;
  - servidor ELM327 na porta `portas.elm327_tcp` (35000), a menos que `--sem-elm327`;
  - o coletor, com transporte e publicador escolhidos pela configuração (`build_transport`, `build_publisher`).
  Todos compartilham o mesmo `Simulator`, então um override feito no painel muda a leitura do coletor.
- Encerramento limpo com Ctrl+C e SIGTERM (fecha coletor, servidores e banco, sem traceback).
- Portas e caminho do banco sobrescrevíveis por argumento (para os testes usarem portas livres).
- `Makefile`: `make run` passa a executar `python -m obd run`.
- `docker/app.Dockerfile` e serviço `app` em `docker-compose.yml` (portas 8000, 8001 e 35000), mantendo o perfil `mqtt` do Mosquitto. O serviço `app` não depende do broker.
- `README.md`: seção "Como rodar" com as URLs `http://localhost:8000/` (dashboard) e `http://localhost:8001/` (painel), e o aviso de que abrir os HTML por servidor estático (Live Server) mostra a tela sem dados.

## Testes (escrever primeiro)

Teste de integração que inicia `python -m obd run` como subprocesso, com portas livres e banco temporário:

- `GET /healthz` responde em até 10 s.
- Em até 10 s, `GET /api/latest` traz valores de rotação, velocidade e temperatura.
- `WS /ws/stream` entrega pelo menos 5 amostras em 5 s.
- `PUT /sim/override/rpm` com 3000 na porta do painel: `/api/latest` mostra rotação de 3000 (tolerância de resolução) em até 2 s.
- `POST /sim/dtc` com P0300: `/api/dtc` lista P0300 e o MIL aparece nos dados.
- Um cliente de soquete cru em 35000 recebe `41 0C ...` para `010C`.
- SIGINT encerra o processo com código 0 em até 5 s.

Se o Playwright e o Chromium instalarem no ambiente, capture o dashboard e o painel com dados reais em `docs/img/` (um PNG de cada) e confira que a tela não está em "reconectando". Se não instalarem, registre em `docs/duvidas.md`.

## Critério de pronto

```bash
pytest -q --tb=short tests/integration -k run
make lint
make run        # sobe tudo; Ctrl+C encerra
```

Cobre a fase de integração do MVP (RF01 a RF09 juntos) e RF10 no mesmo processo.

## Fora desta tarefa

TLS, autenticação e implantação em nuvem.

## Prompt de lançamento

```text
Leia apenas tasks/13-run-orquestracao.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
