// Ajustes do adaptador. Mude aqui antes de gravar.
#pragma once

// Pinos do TWAI ligados ao SN65HVD230 (TX -> pino D/TXD, RX -> pino R/RXD do módulo).
#define CAN_TX_PIN 5
#define CAN_RX_PIN 4

// 1 = ECU falsa com valores fixos, sem CAN (valida Wi-Fi e a suíte sem carro).
#define BENCH_MODE 1

// 1 = ponto de acesso (celular ou PC conecta ao ESP32, IP 192.168.0.10);
// 0 = estação (o ESP32 entra na sua rede e responde pelo nome mDNS).
#define WIFI_AP_MODE 1
#define WIFI_AP_SSID "OBD-ESP32"
#define WIFI_AP_PASSWORD "obd12345"  // mínimo de 8 caracteres
#define WIFI_STA_SSID "sua-rede"
#define WIFI_STA_PASSWORD "sua-senha"
#define MDNS_NAME "obd-esp32"  // obd-esp32.local

#define TCP_PORT 35000

// 1 = aceita o modo 04 (apagar falhas). Deixe em 0: o objetivo é só coletar.
#define ALLOW_CLEAR_DTC 0

// Tempo máximo pela primeira resposta da ECU (ms).
#define ECU_TIMEOUT_MS 200
