---
id: "06"
title: Servidor, API e banco de dados
model: haiku
session: 7
order: 7
depends_on: ["01"]
parallel_with: ["02", "03", "04", "05"]
weight: M
escalate_if: "o WebSocket ou a detecção de perda por seq falha após 2 iterações; passar para sonnet"
spec: docs/spec/05-api.md, docs/spec/07-dados-web.md
---

## Escopo

Implementar `src/obd/server/` com FastAPI, SQLAlchemy e SQLite. Usa apenas os schemas de `protocol/schemas.py` (tarefa 01), então roda em paralelo com as tarefas 02 a 05.

## Arquivos

- `models.py`: tabelas `runs`, `samples`, `readings`, `dtc_events` e `comm_events`, com índices e `UNIQUE(run_id, seq)`.
- `storage.py`: interface `Storage`, `SqlStorage` (aiosqlite) e `InMemoryStorage` para testes.
- `routes.py`: `POST /api/ingest/sample`, `POST /api/ingest/dtc`, `GET /api/latest`, `GET /api/history`, `GET /api/dtc`, `GET /api/stats`, `GET /api/export.csv` e `GET /healthz`.
- `ws.py`: `WS /ws/stream`, que reenvia as últimas 60 s ao conectar e depois transmite cada amostra e cada relatório de DTC.
- `app.py`: fábrica da aplicação; serve estáticos de `src/obd/web/dashboard/` em `/`.
- Estatísticas: contagem, perdas e duplicações por `seq`, latência (média, p95, p99, máximo) e taxa de atualização.

## Testes (escrever primeiro)

- `httpx.AsyncClient` com `InMemoryStorage`: ingestão, consulta, exportação e saúde.
- Perda e duplicação: uma sequência com lacuna e um `seq` repetido são contados corretamente.
- WebSocket: um cliente conectado recebe a amostra ingerida depois e o histórico de 60 s ao entrar.
- Persistência em SQLite temporário: reiniciar a aplicação preserva os dados.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration
make lint
```

Cobre RF07, RF08 e RNF02 (p95 abaixo de 50 ms na ingestão local).

## Fora desta tarefa

Dashboard visual (tarefa 07) e painel do simulador (tarefa 08).

## Prompt de lançamento

```text
Leia apenas tasks/06-servidor-banco.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
