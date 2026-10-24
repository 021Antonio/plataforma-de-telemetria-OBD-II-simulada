# 5. API e conexões

## Portas e processos

| Processo | Porta | Protocolo | Quem se conecta |
| --- | --- | --- | --- |
| Servidor da plataforma | 8000 | HTTP e WebSocket | Navegador, coletor |
| Simulador (controle) | 8001 | HTTP e WebSocket | Painel de controle |
| Simulador (ELM327) | 35000 | TCP | Coletor, apps OBD de terceiros |
| Mosquitto (opcional) | 1883 | MQTT | Coletor, servidor |

No modo padrão o coletor fala com a ECU simulada pelo barramento CAN virtual, no mesmo processo ou em outro com `python-can`. No modo ELM327, ele abre um socket em `localhost:35000`, exatamente como faria com um adaptador Wi-Fi real em `192.168.0.10:35000`.

## Servidor da plataforma (porta 8000)

| Método e rota | Função | Resposta |
| --- | --- | --- |
| `POST /api/ingest/sample` | Recebe uma amostra do coletor | `202` |
| `POST /api/ingest/dtc` | Recebe um relatório de DTCs | `202` |
| `GET /api/latest` | Última amostra e estado dos DTCs | `Sample` |
| `GET /api/history?since=&limit=` | Histórico de amostras | lista de `Sample` |
| `GET /api/dtc` | DTCs ativos e histórico | lista de `DtcReport` |
| `GET /api/stats` | Contagens, latência, perdas, taxa de atualização | `Stats` |
| `GET /api/export.csv?since=` | Exportação para análise | CSV |
| `GET /healthz` | Verificação de saúde | `200` |
| `WS /ws/stream` | Fluxo em tempo real de amostras e DTCs | mensagens JSON |

## Simulador (porta 8001)

| Método e rota | Função | Corpo |
| --- | --- | --- |
| `GET /sim/state` | Estado físico real atual | n/a |
| `PUT /sim/override/{nome}` | Força um valor (rpm, speed, coolant, throttle, fuel, voltage) | `{"value": 3000}` |
| `DELETE /sim/override/{nome}` | Volta ao modelo automático | n/a |
| `POST /sim/profile` | Escolhe o ciclo de condução | `{"name": "urbano"}` |
| `POST /sim/dtc` | Injeta um DTC | `{"code": "P0300", "pending": false}` |
| `DELETE /sim/dtc` | Limpa os DTCs | n/a |
| `PUT /sim/latency` | Faixa de atraso da ECU em ms | `{"min": 8, "max": 14}` |
| `PUT /sim/network` | Taxa de perda e de corrupção | `{"drop": 0.02, "corrupt": 0.0}` |
| `POST /sim/unresponsive` | ECU sem resposta | `{"on": true}` |
| `POST /sim/seed` | Reinicia com semente | `{"model": 42, "ecu": 7}` |
| `WS /sim/stream` | Estado real a cada passo | JSON |

## Schemas JSON

```jsonc
// Sample  (coletor -> servidor, WS -> dashboard)
{
  "seq": 1042,
  "ts": 1761267012.345,           // instante de publicação (epoch, s)
  "cycle_ms": 113.3,
  "source": "can_virtual",         // ou "elm327_tcp"
  "values": {
    "rpm":       {"pid": "0x0C", "value": 2000.25, "unit": "rpm", "rtt_ms": 11.2},
    "speed":     {"pid": "0x0D", "value": 62,      "unit": "km/h", "rtt_ms": 11.4},
    "coolant":   {"pid": "0x05", "value": 88,      "unit": "C",    "rtt_ms": 10.9}
  },
  "errors": {"timeouts": 0, "invalid": 0}
}

// DtcReport
{
  "ts": 1761267013.1,
  "mil": true,
  "count": 1,
  "codes": [{"code": "P0300", "description": "Falha de ignição aleatória ou em múltiplos cilindros", "status": "stored"}]
}

// Stats
{"received": 2104, "lost": 0, "duplicated": 0,
 "latency_ms": {"mean": 0.64, "p95": 0.89, "p99": 1.79, "max": 4.4},
 "update_rate_hz": 8.8}
```

## Tópicos MQTT (modo opcional)

`telemetria/<veiculo>/dados` (QoS 0) e `telemetria/<veiculo>/dtc` (QoS 1), com o mesmo JSON acima. O servidor assina os dois e grava no banco.

## Regras de conexão

- O coletor reconecta com recuo exponencial (1 s, 2 s, 4 s, até 30 s) e registra cada tentativa.
- O número de sequência (`seq`) é contínuo por execução. O servidor detecta lacunas e duplicações a partir dele.
- O WebSocket reenvia as últimas 60 s ao conectar, para o dashboard não abrir vazio.
