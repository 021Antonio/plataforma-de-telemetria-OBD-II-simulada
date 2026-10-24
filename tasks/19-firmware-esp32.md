---
id: "19"
title: Firmware do ESP32 DevKit como adaptador ELM327 por Wi-Fi
model: sonnet
session: 20
order: 20
depends_on: ["17", "18"]
parallel_with: []
weight: G
escalate_if: "o ISO-TP multiquadro (VIN, DTCs) falha em algum comprimento após 2 iterações: usar opus uma vez"
spec: docs/spec/09-elm327-dialeto.md, docs/spec/04-protocolo.md
---

## Escopo

Firmware para o ESP32 DevKit (ESP32-WROOM-32) com um transceptor SN65HVD230 que age como adaptador ELM327 por Wi-Fi: servidor TCP na porta 35000, traduzindo comandos ELM327 para quadros CAN (500 kbit/s, 11 bits, `0x7DF` e `0x7E8`). O objetivo é só coletar (modos 01, 02, 03, 09). Esta tarefa não consegue gravar nem testar em hardware: o código é testado no PC e a gravação e o ensaio na bancada e no carro são do autor.

Peso G: se o contexto passar de 60%, dividir em duas sessões (19a: biblioteca e testes no PC; 19b: camadas do ESP32 e documentação).

## Arquivos

- `firmware/lib/elm327/`: biblioteca em C++17 pura, sem Arduino nem ESP-IDF: interpretador de comandos AT, formatação das respostas (`ATH`, `ATS`, `ATE`, `ATL`), `SEARCHING...`, ISO-TP com controle de fluxo (quadro de fluxo no `0x7E0`) e remontagem multiquadro. A camada CAN entra por uma interface (`ICanBus`) para poder ser substituída por um dublê no PC.
- `firmware/src/main.cpp` e `firmware/src/`: Wi-Fi (modo ponto de acesso `192.168.0.10` como padrão e modo estação com nome mDNS configurável), servidor TCP 35000, driver TWAI do ESP32 com os pinos de TX e RX configuráveis em `firmware/include/config.h`, e um **modo de bancada** que responde como ECU falsa com valores fixos (sem CAN) para validar Wi-Fi e a suíte sem carro.
- `firmware/platformio.ini`: ambientes `esp32dev` (firmware) e `native` (testes no PC).
- `firmware/test/`: testes em C++ no PC, com `g++` e um cabeçalho de asserções simples, executados por `make -C firmware test` (sem rede e sem PlatformIO).
- `firmware/tools/host_server.cpp`: servidor TCP do PC que usa a biblioteca e o modo de bancada, para rodar a suíte de conformidade da tarefa 17 contra o código do firmware: `python -m tests.conformance --host 127.0.0.1 --port <porta>`.
- `docs/hardware/esp32.md`: lista de peças (ESP32 DevKit, módulo SN65HVD230, conector OBD-II macho, conversor buck de 12 V para 5 V, fusível, diodo de proteção), ligações (TX e RX do TWAI ao módulo, CAN-H no pino 6 e CAN-L no pino 14 do conector, 12 V no pino 16, terra nos pinos 4 e 5), remoção do resistor de terminação de 120 Ω do módulo, e o passo a passo de gravação com PlatformIO em `.venv`.
- `docs/ensaios.md`: seção "Firmware ESP32 (pendente do autor)" com o procedimento de bancada e de campo e a tabela a preencher.

## Testes (escrever primeiro)

- Formatação de cada comando do dialeto igual ao `tests/conformance/dourado.json`.
- ISO-TP: remontagem de 1 a 4095 bytes com quadros fora de ordem, quadro de fluxo e timeout de consecutivo.
- Contra o `host_server`, a suíte de conformidade (tarefa 17) sai com 0 divergências no modo de bancada.
- Só consultas dos modos 01, 02, 03 e 09 são aceitas: o modo `04` (apagar falhas) responde `NO DATA` no firmware, por padrão.

## Critério de pronto

```bash
make -C firmware test
python -m tests.conformance --host 127.0.0.1 --port 35100   # com firmware/tools/host_server ativo
make lint
```

## Fora desta tarefa

Gravar no ESP32, ensaio em carro, Bluetooth e MQTT direto do ESP32. O build com PlatformIO (`esp32dev`) fica documentado, mas não é verificado na execução noturna (depende de baixar a plataforma).

## Prompt de lançamento

```text
Leia apenas tasks/19-firmware-esp32.md, docs/spec/09-elm327-dialeto.md e docs/spec/04-protocolo.md. Testes primeiro, depois a biblioteca em C++ e o servidor de PC; rode os comandos do critério de pronto e mostre só as falhas.
```
