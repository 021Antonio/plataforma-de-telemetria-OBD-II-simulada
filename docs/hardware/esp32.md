# Adaptador ELM327 por Wi-Fi com ESP32 DevKit

Firmware em `firmware/`. A biblioteca (`firmware/lib/elm327/`) é C++17 puro e roda nos testes do PC; só `firmware/src/` depende do ESP32. Gravação e ensaio em bancada e no carro são do autor: nada disto foi gravado ou testado em hardware.

## Lista de peças

| Peça | Observação |
| --- | --- |
| ESP32 DevKit (ESP32-WROOM-32) | O TWAI é o controlador CAN interno |
| Módulo transceptor SN65HVD230 | Alimentado em 3,3 V; o ESP32 não fala CAN sem ele |
| Conector OBD-II macho (J1962) | Para ligar na porta do carro |
| Conversor buck 12 V para 5 V | Alimenta o DevKit pelo pino VIN/5V |
| Fusível de 1 A em série com o 12 V | Protege a fiação |
| Diodo de proteção (ex.: 1N5819) em série com o 12 V | Contra polaridade invertida |

## Ligações

| Origem | Destino |
| --- | --- |
| Conector pino 6 (CAN-H) | CANH do módulo |
| Conector pino 14 (CAN-L) | CANL do módulo |
| Conector pino 16 (12 V) | Fusível, diodo, entrada do buck |
| Conector pinos 4 e 5 (terra) | Terra comum (buck, módulo, ESP32) |
| Saída 5 V do buck | VIN (5 V) do DevKit |
| 3V3 do DevKit | VCC do módulo |
| GPIO 5 (`CAN_TX_PIN`) | TXD (D) do módulo |
| GPIO 4 (`CAN_RX_PIN`) | RXD (R) do módulo |

Os pinos mudam em `firmware/include/config.h`. **Remova o resistor de terminação de 120 Ω do módulo** (ou o jumper de terminação): o carro já tem as terminações e uma a mais derruba o barramento. O pino Rs do SN65HVD230 vai ao terra (modo de alta velocidade).

## Gravação com PlatformIO

```bash
python -m venv .venv && . .venv/bin/activate
pip install platformio
cd firmware
pio run -e esp32dev -t upload     # baixa a plataforma na primeira vez
pio device monitor
```

Este passo **não é verificado na execução noturna** (depende de baixar a plataforma). Os testes que valem para o código são `make -C firmware test` e a suíte de conformidade contra o `host_server`.

## Modos

- **Bancada** (`BENCH_MODE 1`, padrão): ECU falsa com valores fixos, sem CAN. Serve para validar o Wi-Fi e a suíte sem carro.
- **Carro** (`BENCH_MODE 0`): TWAI a 500 kbit/s, 11 bits, requisição em `0x7DF`, resposta em `0x7E8`, filtro de aceitação em `0x7E8`–`0x7EF`.
- **Wi-Fi**: ponto de acesso `OBD-ESP32` em `192.168.0.10` (padrão) ou estação com nome mDNS `obd-esp32.local` (`WIFI_AP_MODE 0`). Servidor TCP na porta 35000.
- **Só coleta**: modos 01, 02, 03 e 09. O modo `04` responde `NO DATA` sem chegar ao barramento (`ALLOW_CLEAR_DTC 0`).

## Conferir no PC

```bash
make -C firmware test
make -C firmware host_server && firmware/build/host_server 35100 &
python -m tests.conformance --host 127.0.0.1 --port 35100
```

Contra o ESP32 em modo de bancada, a mesma suíte com `--host 192.168.0.10 --port 35000`.

## Guias passo a passo

- [`manual-montagem.md`](manual-montagem.md): lista de compras, montagem, gravação, testes e validação por fases (bancada, transceptor, alimentação, carro).
- [`voltar-ao-simulador.md`](voltar-ao-simulador.md): plano B, como seguir só com o simulador se o hardware não for adiante.
- `scripts/coletar_adaptador.py`: coleta de um adaptador ELM327 remoto (o ESP32) com o mesmo coletor do simulador.
