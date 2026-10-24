from fakes import FakeClock
from obd.protocol.dtc import code_to_bytes
from obd.protocol.pids import decode_monitor_status, get_pid
from obd.protocol.services import build_request, parse_response
from obd.simulator.ecu import Ecu
from obd.simulator.faults import FaultInjector
from obd.simulator.vehicle_model import VehicleConfig, VehicleModel, load_profile
from obd.transport.loopback import LoopbackTransport


def build(
    seed: int = 1, profile: str = "urbano"
) -> tuple[LoopbackTransport, Ecu, VehicleModel, FaultInjector, FakeClock]:
    clock = FakeClock()
    model = VehicleModel(load_profile(profile), clock, seed=seed, config=VehicleConfig())
    faults = FaultInjector(seed=seed + 100)
    ecu = Ecu(model, clock, seed=seed + 200, faults=faults)
    return LoopbackTransport(ecu, clock=clock, sleep=clock.sleep), ecu, model, faults, clock


async def read(t: LoopbackTransport, mode: int, pid: int | None = None) -> bytes:
    req = build_request(mode, pid)
    raw = await t.request(req)
    assert raw is not None
    return raw


async def test_real_model_values_match_ecu_log() -> None:
    t, ecu, _, _, clock = build()
    clock.advance(20.0)
    for pid in (0x0C, 0x0D, 0x05, 0x0B):
        req = build_request(1, pid)
        resp = parse_response(await read(t, 1, pid), req)
        d = get_pid(pid)
        assert abs(d.decode(resp.data) - ecu.log[-1][1]) <= d.resolution / 2 + 1e-9


async def test_dtc_in_mode03_lights_mil_and_mode04_clears() -> None:
    t, ecu, _, faults, clock = build()
    clock.advance(30.0)
    faults.schedule_dtc("P0300")
    assert await read(t, 3) == b"\x43\x01" + code_to_bytes("P0300")
    status = decode_monitor_status((await read(t, 1, 1))[2:])
    assert status.mil and status.dtc_count == 1
    assert await read(t, 4) == b"\x44"
    assert await read(t, 3) == b"\x43\x00"
    status = decode_monitor_status((await read(t, 1, 1))[2:])
    assert not status.mil and status.dtc_count == 0


async def test_freeze_frame_keeps_values_at_failure_time() -> None:
    t, ecu, model, faults, clock = build()
    clock.advance(25.0)  # urbano em cruzeiro (50 km/h)
    speed_then = model.value(0x0D)
    faults.schedule_dtc("P0300")
    ecu.poll()  # a ECU aplica o DTC devido na primeira atividade e captura o freeze frame
    clock.advance(30.0)  # veículo já parou
    assert model.value(0x0D) < speed_then - 20
    req = build_request(2, 0x0D)
    raw = await t.request(req)
    assert raw is not None
    resp = parse_response(raw, req)
    assert abs(get_pid(0x0D).decode(resp.data) - speed_then) <= 0.5 + 1e-9
    await read(t, 4)
    assert await t.request(req) is None  # Modo 04 apaga o freeze frame


async def test_whole_stack_is_deterministic() -> None:
    async def trace(seed: int) -> list[bytes]:
        t, _, _, faults, clock = build(seed)
        faults.set_frame_loss(0.2)
        faults.set_corruption(0.2)
        faults.set_delay(1, 5)
        out: list[bytes] = []
        for _ in range(60):
            clock.advance(0.5)
            raw = await t.request(build_request(1, 0x0C))
            out.append(raw or b"")
        return out

    assert await trace(3) == await trace(3)
