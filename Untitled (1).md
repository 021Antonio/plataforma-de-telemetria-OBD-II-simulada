# Spec: Plataforma de Telemetria OBD-II Simulada

Oct 24, 2026 · @Antonio

Esta spec define uma plataforma em software que simula um veículo OBD-II e coleta, decodifica, armazena e exibe sua telemetria por HTTP e WebSocket, sem hardware, com a camada de transporte pronta para receber ESP32, ELM327 ou CAN real depois.

## 1. Visão geral e escopo

O sistema reproduz em software a cadeia completa de telemetria veicular: um simulador responde como uma ECU (ISO 15765-4), um coletor requisita e decodifica PIDs e DTCs, um servidor armazena e distribui, e um dashboard mostra tudo em tempo real.

**Objetivo:** projetar, implementar e validar por testes automatizados uma plataforma aberta de telemetria OBD-II, independente de hardware, com transporte plugável.

**Dentro do escopo**

- Simulador de ECU com modelo de veículo, ciclos de condução e injeção de falhas.
- Protocolo OBD-II sobre CAN: Modos 01, 02, 03, 04, 07 e 09, ISO-TP completo, descoberta de PIDs (0x00, 0x20, 0x40).
- Camada de compatibilidade ELM327 por socket TCP (comandos AT e OBD).
- Coletor (equivalente lógico do firmware do ESP32), servidor HTTP/WebSocket, banco de dados e dashboard.
- Painel de controle do simulador (sliders, botões de falha, perfis).
- Testes automatizados e coleta de métricas de exatidão, latência e taxa de atualização.

**Fora do escopo (declarado como limitação ou trabalho futuro)**

- Hardware embarcado (ESP32, SN65HVD230, ESP8266) e ensaio em veículo real.
- Camada física CAN (níveis elétricos, terminação, ACK entre nós).
- K-Line, J1850 e CAN de 29 bits.
- Comandos de atuação no veículo: o sistema é somente leitura.
- Bluetooth, TLS e aplicativo móvel.

**Premissas**

- Execução em um PC com Python 3.12 ou superior e Docker opcional.
- Todos os valores simulados têm valor físico real conhecido, o que permite medir o erro de decodificação.
- O simulador não pretende reproduzir um veículo específico, apenas gerar sinais coerentes.

## 2. Requisitos

Cada requisito tem um identificador e um critério de aceitação verificável por teste.

**Funcionais**

| ID | Requisito | Critério de aceitação |
| --- | --- | --- |
| RF01 | Simulador responde ao Modo 01 para os PIDs configurados | Resposta em 0x7E8 com modo + 0x40 e PID repetido |
| RF02 | Descoberta de PIDs suportados (0x00, 0x20, 0x40) | Máscara de 32 bits correta; coletor pede só PIDs suportados |
| RF03 | Leitura de DTCs (Modo 03), pendentes (Modo 07) e limpeza (Modo 04) | P0300 injetado aparece em até 2 ciclos de consulta; Modo 04 zera a lista |
| RF04 | Dados congelados (Modo 02) ao surgir uma falha | Freeze frame com os PIDs do instante da falha |
| RF05 | ISO-TP completo (primeiro quadro, consecutivos, controle de fluxo) | VIN de 17 caracteres lido via Modo 09 PID 0x02 |
| RF06 | Coletor requisita, valida e decodifica PIDs pelas fórmulas SAE J1979 | Erro máximo ≤ metade da resolução em 100% das leituras |
| RF07 | Servidor recebe a telemetria e a persiste | Nenhuma perda ou duplicação pelo número de sequência |
| RF08 | API HTTP de consulta e WebSocket de tempo real | Dashboard atualiza sem recarregar |
| RF09 | Painel de controle altera o simulador em tempo de execução | Mudança refletida na leitura em até 2 ciclos |
| RF10 | Camada ELM327 por TCP | Um cliente ELM327 comum completa ATZ, ATE0, 0100 e 010C |
| RF11 | Injeção de falhas de comunicação (atraso, perda, resposta inválida, sem resposta) | Coletor se recupera sem travar e registra o evento |
| RF12 | Transporte plugável por configuração | Trocar simulador por ELM327/TCP ou serial sem alterar o código do coletor |

**Não funcionais**

| ID | Requisito | Meta |
| --- | --- | --- |
| RNF01 | Tempo de ciclo de 10 PIDs | ≤ 150 ms com ECU em 10 ms |
| RNF02 | Latência coletor ao banco | p95 ≤ 50 ms |
| RNF03 | Perda de mensagens | 0 em ensaio de 240 s |
| RNF04 | Conformidade com ISO 15765-4 | 11 bits, 500 kbit/s, P2 = 50 ms |
| RNF05 | Reprodutibilidade | Sementes fixas e ensaios repetíveis em 2 máquinas |
| RNF06 | Cobertura de testes | ≥ 80% nos módulos de protocolo |
| RNF07 | Instalação | Um comando (`docker compose up` ou `make run`) |
| RNF08 | Segurança | Somente leitura; API local, sem exposição externa por padrão |

## 3. Arquitetura

O coletor só conhece a interface `Transport`. Trocar o simulador por um adaptador ELM327 ou por um ESP32 muda a classe de transporte e mais nada.

&#91;embedded content: arquitetura · 6 módulos, 1 interface de transporte\]

**Fluxo de dados**

1. O painel de controle altera o simulador por HTTP.
2. O coletor pede PIDs ao transporte e a ECU virtual responde.
3. O coletor publica um `Sample` por HTTP, WebSocket ou MQTT.
4. O servidor grava no SQLite e repassa por WebSocket.
5. O dashboard desenha os valores e o estado dos DTCs.

## 4. Stack e estrutura do repositório

| Camada | Escolha | Motivo |
| --- | --- | --- |
| Linguagem | Python 3.12+ | Reaproveita o ambiente do TCC e o `python-can` |
| Servidor | FastAPI + Uvicorn | HTTP, WebSocket e OpenAPI automático |
| Assíncrono | `asyncio` | Coletor, simulador e servidor no mesmo processo ou separados |
| CAN virtual | `python-can` (interface `virtual`) | Barramento CAN em memória, trocável por `socketcan` ou `slcan` |
| Banco | SQLite via SQLAlchemy 2 | Zero configuração, fácil de reproduzir |
| Mensageria (opcional) | MQTT com Mosquitto | Mantém a trilha do TCC; ativada por configuração |
| Front-end | HTML + JavaScript puro, SVG para os manômetros | Funciona offline e sem build |
| Testes | pytest, pytest-asyncio, hypothesis | Unitário, propriedade e integração |
| Qualidade | ruff, mypy, pre-commit | Padronização |
| Execução | Docker Compose e Makefile | RNF07 |

**Estrutura de diretórios**

```text
obd-telemetry/
  pyproject.toml
  Makefile
  docker-compose.yml
  config/
    default.yaml            # transporte, PIDs, taxas, portas
    profiles/               # ciclos de condução e cenários de falha (YAML)
  src/obd/
    protocol/               # núcleo puro, sem I/O
      pids.py               # tabela de PIDs, fórmulas de encode/decode
      dtc.py                # codificação e descrição de DTCs
      frames.py             # montagem e validação de quadros CAN 11 bits
      isotp.py              # transporte ISO-TP (SF, FF, CF, FC)
      services.py           # modos 01, 02, 03, 04, 07, 09
    transport/              # como os bytes chegam à ECU
      base.py               # interface Transport
      can_virtual.py        # python-can virtual
      elm327_tcp.py         # cliente ELM327 por socket
      serial_port.py        # reservado para ESP32 ou ELM327 serial
      loopback.py           # para testes
    simulator/
      vehicle_model.py      # física simplificada e ciclo de condução
      ecu.py                # ECU virtual (responde ISO 15765-4)
      faults.py             # injeção de falhas e atrasos
      elm327_server.py      # servidor TCP compatível com ELM327
      control_api.py        # rotas do painel de controle
    collector/
      collector.py          # laço de aquisição por PID e DTC
      scheduler.py          # prioridade e taxa por PID
      publisher.py          # envia ao servidor (HTTP, WS ou MQTT)
    server/
      app.py                # FastAPI
      routes.py             # REST
      ws.py                 # WebSocket e SSE
      storage.py            # SQLAlchemy
      models.py             # tabelas e schemas Pydantic
    web/
      dashboard/            # index.html, app.js, gauges.js
      simulator_panel/      # painel de controle
  tests/
    unit/  integration/  e2e/  benchmarks/
  docs/
    spec.md  ensaios.md
```

## 5. Módulos e interfaces

O núcleo `protocol/` não faz I/O e não depende de nenhum outro módulo. Todo o resto depende dele e das interfaces abaixo. Isso permite testar o protocolo sem rede e trocar o transporte sem tocar no coletor.

| Módulo | Responsabilidade | Depende de |
| --- | --- | --- |
| `protocol` | Fórmulas, quadros, ISO-TP, serviços, DTCs | nada |
| `transport` | Enviar e receber quadros OBD (bytes de dados) | `protocol` |
| `simulator` | ECU virtual, modelo de veículo, falhas, servidor ELM327 | `protocol`, `transport` |
| `collector` | Requisitar, validar, decodificar e publicar | `protocol`, `transport` |
| `server` | API, WebSocket, persistência | `protocol` (schemas) |
| `web` | Dashboard e painel de controle | API do `server` e do `simulator` |

**Contratos principais**

```python
# transport/base.py
class Transport(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        """Envia uma requisição OBD (ex.: 01 0C) e devolve a resposta completa
        já remontada pelo ISO-TP. None se estourar o tempo."""
    @property
    def name(self) -> str: ...

# protocol/pids.py
@dataclass(frozen=True)
class PidDef:
    pid: int
    name: str
    unit: str
    n_bytes: int
    resolution: float
    decode: Callable[[bytes], float]
    encode: Callable[[float], bytes]       # usado pela ECU simulada

# protocol/services.py
def build_request(mode: int, pid: int | None = None) -> bytes: ...
def parse_response(raw: bytes) -> Response:       # valida modo+0x40 e PID
    ...

# simulator/vehicle_model.py
class VehicleModel(Protocol):
    def step(self, dt: float) -> VehicleState: ...    # valor físico real
    def set_override(self, name: str, value: float | None) -> None: ...

# simulator/faults.py
class FaultInjector(Protocol):
    def add_dtc(self, code: str) -> None: ...
    def clear_dtcs(self) -> None: ...
    def set_response_delay(self, ms_min: int, ms_max: int) -> None: ...
    def set_drop_rate(self, p: float) -> None: ...          # 0..1
    def set_corruption_rate(self, p: float) -> None: ...
    def set_unresponsive(self, on: bool) -> None: ...

# collector/publisher.py
class Publisher(Protocol):
    async def publish_sample(self, sample: Sample) -> None: ...
    async def publish_dtcs(self, report: DtcReport) -> None: ...

# server/storage.py
class Storage(Protocol):
    async def save_sample(self, s: Sample, recv_ts: float) -> None: ...
    async def save_dtcs(self, r: DtcReport, recv_ts: float) -> None: ...
    async def history(self, since: float, limit: int) -> list[Sample]: ...
    async def stats(self) -> Stats: ...
```

**Coletor: comportamento**

1. Na abertura, consulta os PIDs suportados (0x00, 0x20, 0x40) e guarda a lista.
2. Monta o plano de leitura: PIDs rápidos (rotação, MAP, borboleta) a cada ciclo, PIDs lentos (temperaturas, combustível, tensão) a cada N ciclos.
3. Para cada PID: envia, valida o eco de modo e PID, decodifica, mede o RTT.
4. A cada 2 s lê o PID 0x01 (MIL e contagem) e, se houver mudança, lê o Modo 03.
5. Ao fim do ciclo, publica um `Sample` com número de sequência e instante.
6. Em timeout, registra o evento, segue para o próximo PID e aplica recuo progressivo se houver falhas seguidas.

## 6. Protocolo OBD-II

**Quadros CAN (ISO 15765-4, 11 bits, 500 kbit/s)**

| Campo | Valor |
| --- | --- |
| Requisição funcional | ID `0x7DF` (todas as ECUs) ou físico `0x7E0` a `0x7E7` |
| Resposta da ECU do motor | ID `0x7E8` |
| Tamanho do quadro | Sempre 8 bytes, com preenchimento `0x55` nos bytes não usados |
| Tempo máximo de resposta (P2) | 50 ms |
| Tempo de quadro (pior caso, 8 bytes) | 270 µs (C = 47 + 8s + ⌊(34 + 8s − 1)/4⌋) |

**ISO-TP (primeiro byte do campo de dados)**

| Tipo | Byte PCI | Conteúdo |
| --- | --- | --- |
| Quadro único (SF) | `0x0N` | N = bytes úteis (1 a 7) |
| Primeiro quadro (FF) | `0x1L LL` | Comprimento total em 12 bits, depois 6 bytes de dados |
| Quadro consecutivo (CF) | `0x2S` | S = sequência 0 a F, 7 bytes de dados |
| Controle de fluxo (FC) | `0x30 BS STmin` | Enviado pelo coletor após o FF: continuar, bloco, espaçamento |

A ECU simulada envia o FF, espera o FC, envia os CFs respeitando `STmin` e `BS`. O coletor remonta e valida o comprimento. Estouro de N\_Cr (1 s) aborta a recepção.

**Serviços (modos)**

| Modo | Requisição | Resposta | Observação |
| --- | --- | --- | --- |
| 01 | `01 PID` | `41 PID dados` | Dados atuais |
| 02 | `02 PID 00` | `42 PID 00 dados` | Freeze frame |
| 03 | `03` | `43 N` + N×2 bytes | N = número de DTCs (em CAN) |
| 04 | `04` | `44` | Limpa DTCs e freeze frame |
| 07 | `07` | `47 N` + N×2 bytes | DTCs pendentes |
| 09 | `09 02` | `49 02 01` + 17 bytes | VIN, resposta multiquadro |
| negativa | qualquer inválida | `7F modo código` | Ex.: `7F 01 12` (sub-função não suportada) |

PID sem suporte não recebe resposta. O coletor trata isso como timeout apenas se o PID não foi anunciado na descoberta.

**PIDs implementados**

| PID | Grandeza | Bytes | Fórmula | Unidade | Resolução |
| --- | --- | --- | --- | --- | --- |
| 0x00, 0x20, 0x40 | PIDs suportados | 4 | Máscara de 32 bits, bit 31 = primeiro PID da faixa | n/a | n/a |
| 0x01 | Estado do monitor | 4 | A bit 7 = MIL, bits 0 a 6 = nº de DTCs | n/a | n/a |
| 0x04 | Carga calculada | 1 | A·100/255 | % | 0,392 |
| 0x05 | Temp. arrefecimento | 1 | A − 40 | °C | 1 |
| 0x06 | Ajuste combustível curto prazo | 1 | (A − 128)·100/128 | % | 0,781 |
| 0x0B | Pressão do coletor (MAP) | 1 | A | kPa | 1 |
| 0x0C | Rotação | 2 | (256A + B)/4 | rpm | 0,25 |
| 0x0D | Velocidade | 1 | A | km/h | 1 |
| 0x0F | Temp. ar de admissão | 1 | A − 40 | °C | 1 |
| 0x11 | Borboleta | 1 | A·100/255 | % | 0,392 |
| 0x2F | Nível de combustível | 1 | A·100/255 | % | 0,392 |
| 0x42 | Tensão do módulo | 2 | (256A + B)/1000 | V | 0,001 |

**DTC (2 bytes)**

Os dois bits mais altos do primeiro byte dão o sistema (`00` P, `01` C, `10` B, `11` U), os dois seguintes o primeiro dígito (0 a 3) e o restante forma os três dígitos hexadecimais. Exemplo: `03 00` é `P0300`. A tabela de descrições fica em `protocol/dtc.py` e cobre, no mínimo, P0300 a P0304, P0171, P0172, P0420 e P0133.

**Camada ELM327 (porta TCP 35000)**

| Entrada | Saída | Comportamento |
| --- | --- | --- |
| `ATZ` | `ELM327 v1.5` | Reinicia |
| `ATE0`, `ATL0`, `ATS0`, `ATH0` | `OK` | Sem eco, sem avanço de linha, sem espaços, sem cabeçalho |
| `ATSP6` ou `ATSP0` | `OK` | Protocolo CAN 11 bits 500 kbit/s |
| `ATDP` | `ISO 15765-4 (CAN 11/500)` | Protocolo atual |
| `ATRV` | `12.6V` | Tensão lida do modelo |
| `0100` | `41 00 BE 3F A8 13` | Em hexadecimal, com espaços se `ATS1` |
| `010C` | `41 0C 1F 40` | Resposta decodificável |
| `03` | `43 01 03 00` ou `NO DATA` | Sem DTCs |
| comando desconhecido | `?` | Conforme o ELM327 real |
| PID sem suporte | `NO DATA` | Idem |

Toda resposta termina com `\r\r>` (prompt). O primeiro `0100` após `ATZ` pode devolver `SEARCHING...` antes da resposta, como no chip real.

## 7. API e conexões

**Portas e processos**

| Processo | Porta | Protocolo | Quem se conecta |
| --- | --- | --- | --- |
| Servidor da plataforma | 8000 | HTTP e WebSocket | Navegador, coletor |
| Simulador (controle) | 8001 | HTTP e WebSocket | Painel de controle |
| Simulador (ELM327) | 35000 | TCP | Coletor, apps OBD de terceiros |
| Mosquitto (opcional) | 1883 | MQTT | Coletor, servidor |

No modo padrão o coletor fala com a ECU simulada pelo barramento CAN virtual, no mesmo processo ou em outro com `python-can`. No modo ELM327, ele abre um socket em `localhost:35000`, exatamente como faria com um adaptador Wi-Fi real em `192.168.0.10:35000`.

**Servidor da plataforma (porta 8000)**

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

**Simulador (porta 8001)**

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

**Schemas JSON**

```json
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

**Tópicos MQTT (modo opcional)**

`telemetria/<veiculo>/dados` (QoS 0) e `telemetria/<veiculo>/dtc` (QoS 1), com o mesmo JSON acima. O servidor assina os dois e grava no banco.

**Regras de conexão**

- O coletor reconecta com recuo exponencial (1 s, 2 s, 4 s, até 30 s) e registra cada tentativa.
- O número de sequência (`seq`) é contínuo por execução. O servidor detecta lacunas e duplicações a partir dele.
- O WebSocket reenvia as últimas 60 s ao conectar, para o dashboard não abrir vazio.

## 8. Simulador e mocks

**Modelo de veículo (`vehicle_model.py`)**

O modelo avança em passos de 10 ms e mantém o estado físico real, que serve de referência para medir o erro de decodificação. Os valores são ilustrativos de um compacto 1.6 aspirado e podem ser trocados em `config/default.yaml`.

| Variável | Como é calculada |
| --- | --- |
| Velocidade | Segue o perfil de condução com aceleração limitada |
| Marcha | Escolhida pela velocidade (trocas em faixas fixas) |
| Rotação | Pela velocidade, marcha, relação final e raio do pneu (fórmula abaixo); marcha lenta em 800 rpm |
| Borboleta | Pela aceleração pedida pelo perfil |
| Carga e MAP | Crescem com a borboleta e a rotação; MAP limitado à pressão atmosférica (101 kPa), pois o motor é aspirado |
| Temp. arrefecimento | Aproximação exponencial de 25 °C até 90 °C (constante de tempo configurável) |
| Temp. ar de admissão | Ambiente mais um acréscimo lento com a temperatura do motor |
| Ajuste de mistura (STFT) | Oscila em torno de 0 % com amplitude de 3 %, simulando a malha fechada |
| Nível de combustível | Decresce proporcionalmente à carga integrada |
| Tensão | 14,1 V com o motor ligado e 12,4 V desligado |
| Ruído | Gaussiano de baixa amplitude, semente fixa |

```latex
n_{rpm} = \frac{v/3{,}6}{r_{pneu}} \cdot i_{marcha} \cdot i_{final} \cdot \frac{60}{2\pi}
```

**Perfis de condução (YAML)**

```yaml
name: urbano
loop: true
steps:
  - {t: 0,   speed: 0,  throttle: 0.0}      # marcha lenta
  - {t: 10,  speed: 50, throttle: 0.45}     # aceleração
  - {t: 40,  speed: 50, throttle: 0.20}     # cruzeiro
  - {t: 50,  speed: 0,  throttle: 0.0}      # desaceleração e parada
```

Perfis entregues: `parado`, `urbano`, `rodovia`, `ciclo_120s` (o do TCC: marcha lenta, 0 a 80 km/h, cruzeiro e desaceleração) e `esforco` (rotação alta para testar PIDs rápidos).

**Catálogo de falhas (`faults.py`)**

| Falha | Parâmetros | O que testa |
| --- | --- | --- |
| DTC armazenado | código, instante | Modo 03, MIL, freeze frame |
| DTC pendente | código | Modo 07 |
| Atraso de resposta | mínimo e máximo em ms | Sensibilidade (ensaio E2) |
| Perda de quadros | probabilidade | Timeout e recuperação |
| Quadro corrompido | probabilidade | Validação do eco de modo e PID |
| ECU muda | liga e desliga | Recuo progressivo |
| PID não suportado | lista | Descoberta de PIDs (0x00) |
| Resposta negativa | modo e código | Tratamento de `7F` |
| Atraso de ISO-TP | `STmin` e `BS` | Remontagem multiquadro |

**Mocks e dublês de teste**

| Dublê | Substitui | Uso |
| --- | --- | --- |
| `LoopbackTransport` | Barramento e ECU | Testes do coletor sem rede nem simulador |
| `ScriptedTransport` | ECU real | Responde a uma lista fixa de requisições, para casos de borda e quadros inválidos |
| `FakeClock` | Relógio do sistema | Tempo determinístico nos testes de latência, timeout e recuo |
| `FakeVehicleModel` | Modelo físico | Valores constantes ou em rampa para verificar a decodificação |
| `InMemoryStorage` | SQLite | Testes do servidor e do publisher |
| `RecordingPublisher` | Servidor | Verifica o que o coletor publica |
| `FakeElm327Client` | App OBD | Sequências de comandos AT contra o servidor ELM327 |

**Determinismo:** o simulador recebe duas sementes (modelo e ECU) e o relógio é injetável. Com as mesmas sementes e o mesmo perfil, a sequência de valores físicos é idêntica entre execuções.

## 9. Banco de dados e interfaces web

**Esquema SQLite**

| Tabela | Colunas principais | Observação |
| --- | --- | --- |
| `runs` | `id`, `started_at`, `source`, `seed_model`, `seed_ecu`, `profile`, `notes` | Uma linha por execução ou ensaio |
| `samples` | `id`, `run_id`, `seq`, `ts_pub`, `ts_recv`, `latency_ms`, `cycle_ms` | Uma linha por ciclo; `UNIQUE(run_id, seq)` |
| `readings` | `id`, `sample_id`, `pid`, `name`, `value`, `unit`, `rtt_ms`, `true_value` | Uma linha por PID; `true_value` só existe com simulador |
| `dtc_events` | `id`, `run_id`, `ts_recv`, `code`, `status`, `mil` | Mudanças de estado dos DTCs |
| `comm_events` | `id`, `run_id`, `ts`, `kind`, `detail` | Timeouts, quadros inválidos, reconexões |

Índices em `samples(run_id, seq)` e `readings(sample_id, pid)`. A coluna `true_value` é o que permite calcular o erro de decodificação por consulta SQL, sem reler arquivos.

**Dashboard (porta 8000)**

| Elemento | Dados | Comportamento |
| --- | --- | --- |
| Conta-giros | `rpm` | Ponteiro animado, faixa vermelha configurável |
| Manômetro do coletor | `map` | Escala em bar relativo, com vácuo negativo |
| Velocidade, temperatura, combustível | PIDs correspondentes | Mostradores numéricos com cor por faixa |
| Borboleta, carga, ajuste de mistura, tensão | PIDs correspondentes | Barras horizontais |
| Gráfico dos últimos 60 s | Séries selecionáveis | Atualização por WebSocket |
| Diagnóstico | MIL e lista de DTCs | MIL acende com DTC; clicar no código mostra a descrição |
| Cabeçalho | Estado da conexão, taxa (Hz), ciclo (ms), latência | Janela de 3 s |
| Eventos | Timeouts e reconexões | Lista com hora |

Estados da tela: conectado, reconectando e sem dados (fundo cinza e aviso, nunca valores antigos sem marca).

**Painel de controle do simulador (porta 8001)**

| Controle | Ação na API |
| --- | --- |
| Sliders de rotação, velocidade, temperatura, borboleta, combustível e tensão | `PUT /sim/override/{nome}` |
| Botão "voltar ao automático" por variável | `DELETE /sim/override/{nome}` |
| Seletor de perfil de condução | `POST /sim/profile` |
| Lista de falhas com botão de injetar e limpar | `POST` e `DELETE /sim/dtc` |
| Sliders de atraso, perda e corrupção | `PUT /sim/latency` e `/sim/network` |
| Chave "ECU sem resposta" | `POST /sim/unresponsive` |
| Campo de sementes e botão reiniciar | `POST /sim/seed` |
| Monitor de quadros | `WS /sim/stream` mostra requisições e respostas em hexadecimal |

## 10. Testes e critérios de aceitação

**Pirâmide de testes**

| Nível | O que cobre | Ferramenta |
| --- | --- | --- |
| Unitário | Fórmulas de PID, DTC, quadros, ISO-TP, validação de resposta | pytest |
| Propriedade | `decode(encode(x))` dentro de r/2 para 1.001 valores por PID; remontagem ISO-TP para qualquer comprimento de 8 a 4095 bytes | hypothesis |
| Integração | Coletor contra ECU simulada pelo `can_virtual`; servidor com `InMemoryStorage`; servidor ELM327 com cliente falso | pytest-asyncio |
| Ponta a ponta | Simulador, coletor, servidor e WebSocket no ar, com leitura do WebSocket | pytest + processos |
| Desempenho | Ensaios E1, E2 e E3 com coleta de métricas | scripts em `tests/benchmarks` |

**Ensaios de desempenho**

| Ensaio | Cenário | Medidas |
| --- | --- | --- |
| E1 | 240 s, 10 PIDs, ECU em 10 ms ± 3 ms, falha P0300 aos 100 s | Erro por PID, RTT, ciclo, latência, perdas, tempo de detecção da falha |
| E2 | 4 execuções de 30 s com ECU em 0, 10, 25 e 50 ms | Ciclo e taxa em função do atraso |
| E3 | 4 execuções de 20 s com 1, 3, 5 e 10 PIDs | Taxa por PID e leituras por segundo |
| E4 (novo) | Perda de 0, 1, 5 e 10% dos quadros | Timeouts, recuperação, taxa efetiva |
| E5 (novo) | VIN por ISO-TP com `STmin` de 0, 1 e 10 ms | Tempo de remontação |
| E6 (novo) | Cliente ELM327 comum contra o servidor TCP | Compatibilidade de comandos |

Cada ensaio grava um CSV e um JSON em `runs/<data>/` com a configuração e as sementes. A estatística reportada é média, desvio padrão, mediana, p95, p99 e máximo. Repetir cada ensaio em uma segunda máquina, como no TCC, e declarar as diferenças.

**Como o valor real chega para medir o erro**

A ECU simulada registra, para cada resposta, o par `(request_id, true_value)`. O executor de ensaios junta esse registro ao `Sample` pelo `seq`, e grava o resultado em `readings.true_value`. O coletor nunca tem acesso ao valor real.

**Critérios de aceitação do projeto**

- Todos os requisitos RF01 a RF12 com teste automatizado passando.
- RNF01 a RNF04 atendidos nos ensaios E1 a E3.
- Cobertura de testes de pelo menos 80% em `protocol/`.
- `make run` sobe a plataforma completa e o dashboard mostra dados em até 5 s.
- Um cliente ELM327 de terceiros lê rotação e DTCs do servidor TCP.

## 11. Plano de implementação e decisões em aberto

A ordem segue a dependência entre módulos: o núcleo de protocolo primeiro, porque tudo se apoia nele e ele é testável sem rede.

| Fase | Entrega | Pronto quando |
| --- | --- | --- |
| 0. Fundação | Repositório, `pyproject.toml`, ruff, mypy, pytest, Makefile, CI | `make test` roda vazio e passa |
| 1. Núcleo | `protocol/`: PIDs, DTC, quadros, serviços, ISO-TP | Testes unitários e de propriedade verdes |
| 2. Simulador | Modelo, ECU, perfis, falhas, `can_virtual` | Leitor mínimo lê 10 PIDs e DTC contra a ECU |
| 3. Coletor | Descoberta de PIDs, plano de leitura, recuperação, publisher | RF06 e RF11 com testes de integração |
| 4. Servidor | API, WebSocket, SQLite, estatísticas | RF07 e RF08; perda e duplicação detectadas por `seq` |
| 5. Dashboard | Mostradores, gráfico, diagnóstico, eventos | Dados na tela em até 5 s |
| 6. Painel de controle | Sliders, falhas, perfis, monitor de quadros | RF09 |
| 7. ELM327 | Servidor TCP e cliente `elm327_tcp` | RF10 e ensaio E6 |
| 8. Ensaios | E1 a E6, scripts, CSV e gráficos, segunda máquina | RNF01 a RNF06 medidos e documentados |
| 9. Texto | Capítulos reescritos com os números reais | Objetivos, método e resultados coerentes |

O MVP é o fim da fase 5. Depois dele o sistema já demonstra a cadeia inteira, e as fases 6 a 8 acrescentam profundidade e medição.

**Decisões em aberto**

- [ ] O servidor e o simulador rodam no mesmo processo ou em processos separados? Separados é mais fiel e mais fácil de trocar por hardware.
- [ ] MQTT entra na primeira versão ou fica só como adaptador opcional? Sem ele, HTTP e WebSocket bastam.
- [ ] Usar a biblioteca `can-isotp` ou implementar o ISO-TP próprio? Implementar dá conteúdo ao TCC; a biblioteca serve como referência nos testes.
- [ ] Qual será o nome do projeto e do repositório?
- [ ] Haverá um front-end em framework (React) ou fica HTML e JavaScript puro?

**Evolução para hardware (fora desta spec)**

Com a interface `Transport`, o ESP32 com SN65HVD230, um adaptador ELM327 Wi-Fi ou um USB-CAN entram como novas classes de transporte, sem alterar coletor, servidor ou dashboard.
