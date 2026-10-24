from fakes import ScriptedTransport
from obd.transport.base import Transport


async def test_scripted_transport_follows_script() -> None:
    t: Transport = ScriptedTransport({b"\x01\x0d": b"\x41\x0d\x3c"})
    await t.open()
    assert t.name == "scripted"
    assert await t.request(b"\x01\x0d") == b"\x41\x0d\x3c"
    assert await t.request(b"\x01\x0c") is None
    await t.close()
