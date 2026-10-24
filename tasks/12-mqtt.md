---
id: "12"
title: MQTT (publicador, assinante e Mosquitto no Compose)
model: sonnet
session: 8
order: 8
depends_on: ["05", "06"]
parallel_with: ["07", "08", "09"]
weight: M
escalate_if: "o assinante perde mensagens ou duplica registros após 2 iterações"
spec: docs/spec/02-arquitetura-stack.md, docs/spec/05-api.md
---

## Escopo

Adicionar o MQTT como canal alternativo ao HTTP entre coletor e servidor, ativado por configuração. O HTTP continua sendo o padrão.

## Arquivos

- `collector/mqtt_publisher.py`: `MqttPublisher` (interface `Publisher`) com `aiomqtt`. Publica em `telemetria/<veiculo>/dados` (QoS 0) e `telemetria/<veiculo>/dtc` (QoS 1), com o mesmo JSON do HTTP. Reconexão com recuo exponencial (1, 2, 4 até 30 s).
- `server/mqtt_subscriber.py`: assina os dois tópicos, valida com os schemas e grava via `Storage`, igual ao `POST /api/ingest/*`. Mesma detecção de perda e duplicação por `seq`.
- `config/default.yaml`: bloco `publisher: http | mqtt` e dados do broker (host, porta 1883).
- `docker-compose.yml`: serviço `mosquitto` (perfil `mqtt`) e `config/mosquitto.conf` (apenas desenvolvimento local, sem senha). Os serviços do app podem entrar no mesmo arquivo.
- Dependência `aiomqtt` em `pyproject.toml`.

## Testes (escrever primeiro)

- Com um broker falso em memória (`FakeBroker` em `tests/fakes.py`): o coletor publica, o assinante grava, e o resultado é igual ao do caminho HTTP.
- Perda e duplicação por `seq` contadas igual ao HTTP.
- Reconexão: o broker cai e volta, e o coletor retoma sem perder a ordem de `seq`.
- Teste de integração com Mosquitto real, marcado `@pytest.mark.broker` e pulado quando não há broker. Ele não roda no `make test` padrão.
- Trocar `publisher` na configuração não altera o código do coletor.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration -m "not broker"
make lint
```

Cobre RF07 por MQTT e a trilha do TCC original.

## Fora desta tarefa

TLS e autenticação do broker.

## Prompt de lançamento

```text
Leia apenas tasks/12-mqtt.md e as seções de docs/spec citadas nele. Testes primeiro, depois implemente, rode os comandos do critério de pronto e mostre só as falhas.
```
