---
id: "05"
title: Coletor (descoberta, plano de leitura, recuperação e publicação)
model: sonnet
session: 6
order: 6
depends_on: ["03"]
parallel_with: ["06"]
weight: M
escalate_if: "recuo progressivo ou ordem de eventos falham de forma intermitente após 2 iterações"
spec: docs/spec/03-modulos-interfaces.md, docs/spec/05-api.md
---

## Escopo

Implementar `src/obd/collector/`: o equivalente lógico do firmware do ESP32.

## Arquivos

- `collector.py`:
  - descobre PIDs suportados na abertura (0x00, 0x20, 0x40);
  - monta o plano de leitura (PIDs rápidos a cada ciclo, lentos a cada N ciclos);
  - para cada PID envia, valida eco de modo e PID, decodifica e mede o RTT;
  - a cada 2 s lê o PID 0x01 e, se houver mudança, lê o Modo 03.
- `scheduler.py`: prioridade e taxa por PID, configuráveis em `config/default.yaml`.
- `publisher.py`: interface `Publisher`, `HttpPublisher` (POST em `/api/ingest/*`) e `RecordingPublisher` para testes.
- Escolha do transporte por configuração (RF12): `can_virtual`, `loopback` ou `elm327_tcp` (este último chega na tarefa 09).
- Tratamento de falhas: timeout registra evento e segue; falhas seguidas ativam recuo progressivo; `seq` contínuo por execução.

## Testes (escrever primeiro)

- Com `ScriptedTransport` e `FakeClock`: descoberta, plano, timeout, resposta inválida, recuo e retomada.
- Com `LoopbackTransport` e ECU: um ciclo de 10 PIDs gera um `Sample` correto.
- Publicador de teste recebe amostras com `seq` contínuo e sem lacunas.
- Troca de transporte por configuração não altera o código do coletor.
- Medição do ciclo de 10 PIDs com ECU em 10 ms: menor ou igual a 150 ms (RNF01).

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration
make lint
```

Cobre RF02, RF06, RF11, RF12 e RNF01.

## Fora desta tarefa

Servidor, banco e dashboard.

## Prompt de lançamento

```text
Leia apenas tasks/05-coletor.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
