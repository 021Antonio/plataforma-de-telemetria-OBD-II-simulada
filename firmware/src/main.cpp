// Adaptador ELM327 por Wi-Fi: servidor TCP que traduz o dialeto ELM327 para CAN (ou para a
// ECU de bancada). A lógica do dialeto e do ISO-TP está em lib/elm327 e é testada no PC.
#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>

#include "bench.hpp"
#include "config.h"
#include "elm327.hpp"
#if !BENCH_MODE
#include "twai_bus.hpp"
#endif

static WiFiServer server(TCP_PORT);
static WiFiClient client;
static elm327::LineBuffer lines;

#if BENCH_MODE
static elm327::BenchEcu bus;
#else
static TwaiBus bus;
#endif
static elm327::Session* session = nullptr;

static elm327::Options options() {
    elm327::Options o;
    o.allow_clear = ALLOW_CLEAR_DTC;
    o.timing.first_ms = ECU_TIMEOUT_MS;
    return o;
}

static void start_wifi() {
#if WIFI_AP_MODE
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(IPAddress(192, 168, 0, 10), IPAddress(192, 168, 0, 10), IPAddress(255, 255, 255, 0));
    WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD);
    Serial.printf("AP %s em %s\n", WIFI_AP_SSID, WiFi.softAPIP().toString().c_str());
#else
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_STA_SSID, WIFI_STA_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) delay(250);
    Serial.printf("STA em %s\n", WiFi.localIP().toString().c_str());
#endif
    if (MDNS.begin(MDNS_NAME)) MDNS.addService("elm327", "tcp", TCP_PORT);
}

void setup() {
    Serial.begin(115200);
#if !BENCH_MODE
    if (!bus.begin()) Serial.println("TWAI: falha ao iniciar");
#endif
    start_wifi();
    server.begin();
}

void loop() {
    if (!client || !client.connected()) {
        delete session;  // nova conexão = nova sessão (e nova ECU de bancada, se for o caso)
        session = nullptr;
        client = server.available();
        if (!client) return;
        session = new elm327::Session(bus, options());
    }
    char buf[128];
    while (client.available()) {
        const int n = client.read(reinterpret_cast<uint8_t*>(buf), sizeof buf);
        if (n <= 0) break;
        for (const std::string& l : lines.feed(buf, n)) {
            const std::string out = session->handle(l);
            if (!out.empty()) client.write(out.data(), out.size());
        }
    }
}
