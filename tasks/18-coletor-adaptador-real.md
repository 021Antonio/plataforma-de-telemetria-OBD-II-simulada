---
id: "18"
title: Coletor tolerante a respostas de erro, atrasos e quedas de um adaptador real
model: sonnet
session: 19
order: 19
depends_on: ["16", "17"]
parallel_with: []
weight: M
escalate_if: "a reconexão deixa o coletor em estado inconsistente ou há condição de corrida após 2 iterações"
spec: docs/spec/03-modulos-interfaces.md, docs/spec/04-protocolo.md
---

## Escopo

O simulador sempre responde bem. Um adaptador ELM327 real, principalmente um ESP32 por Wi-Fi ligado a um carro, responde com erros, atrasa e perde a conexão. Esta tarefa ajusta o coletor e o transporte `elm327_tcp` para isso, sem alterar o fluxo com o simulador.

## Arquivos

- `src/obd/transport/elm327_tcp.py` e `src/obd/collector/`: tratar `UNABLE TO CONNECT`, `BUS INIT: ERROR`, `CAN ERROR`, `STOPPED`, `BUFFER FULL`, `?` e `NO DATA` como falha de leitura (evento no coletor e sem valor gravado), nunca como dado. A primeira consulta pode demorar vários segundos (`SEARCHING...`): o tempo máximo dessa fase é configurável, separado do tempo das consultas seguintes.
- Tempo limite por consulta configurável em `config/default.yaml` (`coletor.timeout_ms`, padrão compatível com Wi-Fi) e `coletor.timeout_busca_s`.
- Reconexão automática do soquete com recuo progressivo quando o TCP cair, reenviando a sequência de inicialização (`ATZ`, `ATE0`, `ATL0`, `ATS0`, `ATH0`, `ATSP0`) antes de voltar a ler; `seq` nunca pula nem inverte.
- `src/obd/simulator/elm327_server.py`: parâmetro de injeção de erros para testes (lista de respostas de erro a devolver, atraso extra, queda da conexão após N comandos). Fica desligado por padrão.
- `docs/duvidas.md`: registrar o que foi decidido.

## Testes (escrever primeiro)

- Para cada resposta de erro injetada, o coletor registra o evento certo, não grava valor e segue para o próximo PID.
- Queda do TCP no meio da coleta: o coletor reconecta, reinicializa o adaptador e retoma sem duplicar nem inverter `seq`.
- Atraso maior que o tempo limite gera timeout, e atraso menor não.
- Comportamento com o simulador sem injeção permanece igual (os testes existentes passam sem alteração).

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration -m "not broker and not realclient"
make lint
```

## Fora desta tarefa

Transporte serial (Bluetooth) e o firmware.

## Prompt de lançamento

```text
Leia apenas tasks/18-coletor-adaptador-real.md e as seções de docs/spec citadas. Testes primeiro, depois o coletor e o servidor de injeção de erros; rode os comandos do critério de pronto e mostre só as falhas.
```
