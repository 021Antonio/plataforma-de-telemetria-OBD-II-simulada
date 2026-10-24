---
id: "08"
title: API de controle e painel do simulador
model: haiku
session: 10
order: 10
depends_on: ["04"]
parallel_with: ["05", "06", "07", "09", "12"]
weight: P
escalate_if: "overrides não refletem na leitura após 2 iterações; passar para sonnet"
spec: docs/spec/05-api.md, docs/spec/07-dados-web.md
---

## Escopo

Expor o simulador por HTTP e WebSocket (porta 8001) e criar a interface de controle.

## Arquivos

- `simulator/control_api.py`: rotas `GET /sim/state`, `PUT` e `DELETE /sim/override/{nome}`, `POST /sim/profile`, `POST` e `DELETE /sim/dtc`, `PUT /sim/latency`, `PUT /sim/network`, `POST /sim/unresponsive`, `POST /sim/seed` e `WS /sim/stream`.
- `web/simulator_panel/`: `index.html`, `panel.js` e `style.css` com sliders, seletor de perfil, lista de falhas, chave de ECU muda, campo de sementes e monitor de quadros em hexadecimal.
- Validação dos corpos com Pydantic e erros `422` claros.

## Testes (escrever primeiro)

- `httpx`: cada rota altera o estado esperado do simulador.
- Override de rotação em 3000 rpm aparece no `GET /sim/state` e na leitura do PID 0x0C em até 2 ciclos (RF09).
- `DELETE` devolve a variável ao modelo automático.
- Valores fora de faixa são rejeitados.

## Critério de pronto

```bash
pytest -q --tb=short tests/integration
make lint
```

Cobre RF09.

## Fora desta tarefa

Servidor ELM327 (tarefa 09).

## Prompt de lançamento

```text
Leia apenas tasks/08-painel-controle.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
