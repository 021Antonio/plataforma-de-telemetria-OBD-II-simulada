# 3. Módulos e interfaces

O núcleo `protocol/` não faz I/O e não depende de nenhum outro módulo. Todo o resto depende dele e das interfaces abaixo. Isso permite testar o protocolo sem rede e trocar o transporte sem tocar no coletor.

| Módulo | Responsabilidade | Depende de |
| --- | --- | --- |
| `protocol` | Fórmulas, quadros, ISO-TP, serviços, DTCs | nada |
| `transport` | Enviar e receber quadros OBD (bytes de dados) | `protocol` |
| `simulator` | ECU virtual, modelo de veículo, falhas, servidor ELM327 | `protocol`, `transport` |
| `collector` | Requisitar, validar, decodificar e publicar | `protocol`, `transport` |
| `server` | API, WebSocket, persistência | `protocol` (schemas) |
| `web` | Dashboard e painel de controle | API do `server` e do `simulator` |

## Contratos principais

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

## Coletor: comportamento

1. Na abertura, consulta os PIDs suportados (0x00, 0x20, 0x40) e guarda a lista.
2. Monta o plano de leitura: PIDs rápidos (rotação, MAP, borboleta) a cada ciclo, PIDs lentos (temperaturas, combustível, tensão) a cada N ciclos.
3. Para cada PID: envia, valida o eco de modo e PID, decodifica, mede o RTT.
4. A cada 2 s lê o PID 0x01 (MIL e contagem) e, se houver mudança, lê o Modo 03.
5. Ao fim do ciclo, publica um `Sample` com número de sequência e instante.
6. Em timeout, registra o evento, segue para o próximo PID e aplica recuo progressivo se houver falhas seguidas.
