---
id: "07"
title: Dashboard web
model: sonnet
session: 8
order: 8
depends_on: ["06"]
parallel_with: ["05", "08", "09"]
weight: M
escalate_if: "layout ou animação continuam errados após 2 iterações com captura de tela"
spec: docs/spec/07-dados-web.md, docs/spec/05-api.md
---

## Escopo

Dashboard em HTML, CSS e JavaScript puro, sem dependências externas, em `src/obd/web/dashboard/`.

## Arquivos

- `index.html`, `app.js`, `gauges.js` e `style.css`.
- Elementos (ver tabela da spec): conta-giros e manômetro do coletor em SVG, velocidade, temperatura e combustível numéricos, barras de borboleta, carga, ajuste de mistura e tensão, gráfico dos últimos 60 s, painel de diagnóstico com MIL e DTCs, cabeçalho com estado, taxa, ciclo e latência, e lista de eventos.
- Conexão por `WS /ws/stream` com reconexão automática. Estados: conectado, reconectando e sem dados.
- Design claro (fundo branco), legível em tela de notebook.

## Critério de pronto

- Teste automatizado: `GET /` devolve o HTML e o JavaScript não gera erro de sintaxe (`node --check`).
- Teste e2e (opcional com Playwright): injeta uma amostra no servidor e verifica que o valor aparece na tela.
- Checklist manual com captura de tela: valores mudam sem recarregar; MIL acende ao injetar P0300; ao derrubar o servidor aparece "reconectando".

```bash
pytest -q --tb=short tests/e2e
make lint
```

Cobre RF08.

## Fora desta tarefa

Controles do simulador (tarefa 08).

## Prompt de lançamento

```text
Leia apenas tasks/07-dashboard.md e as seções de docs/spec citadas nele. Implemente, valide com captura de tela e rode os comandos do critério de pronto, mostrando só as falhas.
```
