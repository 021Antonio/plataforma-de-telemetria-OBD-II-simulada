# Spec: Plataforma de Telemetria OBD-II Simulada

Plataforma em software que simula um veículo e faz telemetria OBD-II (SAE J1979 sobre CAN, ISO 15765-4). O transporte é plugável: hoje CAN virtual, ELM327 por TCP e loopback; depois ESP32, ELM327 real ou adaptador USB-CAN.

Para economizar tokens, cada tarefa lê **só** a seção que cita.

| Seção | Arquivo | Conteúdo |
|---|---|---|
| 1 | [01-visao-requisitos.md](spec/01-visao-requisitos.md) | Escopo, RF01 a RF12, RNF01 a RNF08 |
| 2 | [02-arquitetura-stack.md](spec/02-arquitetura-stack.md) | Diagrama, stack, estrutura de diretórios |
| 3 | [03-modulos-interfaces.md](spec/03-modulos-interfaces.md) | Módulos e interfaces (Transport, PidDef, VehicleModel, FaultInjector, Publisher, Storage) |
| 4 | [04-protocolo.md](spec/04-protocolo.md) | Quadro CAN, ISO-TP, modos, PIDs, DTCs, ELM327 |
| 5 | [05-api.md](spec/05-api.md) | Portas, rotas REST e WebSocket, schemas JSON, MQTT |
| 6 | [06-simulador.md](spec/06-simulador.md) | Modelo de veículo, perfis, falhas, mocks |
| 7 | [07-dados-web.md](spec/07-dados-web.md) | Esquema SQLite, dashboard, painel de controle |
| 8 | [08-testes.md](spec/08-testes.md) | Pirâmide de testes, ensaios E1 a E6, critérios de aceite |

## Fluxo de trabalho

- Tarefas em [`tasks/`](../tasks), uma por sessão, cada uma com modelo recomendado.
- Ordem, sessões e modelos consolidados em [`PLAN.md`](PLAN.md), gerado pela skill `plan-sessions`.
- Convenções e comandos em [`CLAUDE.md`](../CLAUDE.md).

## Decisões em aberto

1. Servidor e simulador no mesmo processo ou separados (padrão: separados, portas 8000 e 8001).
2. ~~MQTT na v1 ou opcional~~ Decidido: entra na v1 como canal opcional (tarefa 12); HTTP continua o padrão.
3. ISO-TP próprio ou biblioteca `can-isotp` (padrão: implementação própria; a biblioteca serve de referência nos testes).
4. Front-end em JavaScript puro ou React (padrão: JavaScript puro).

Os formatos do ELM327 vêm do conhecimento do protocolo e precisam ser conferidos contra um cliente real (tarefa 09).
