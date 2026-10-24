from obd.protocol.schemas import DtcReport, Sample, Stats


def test_sample_from_spec_json() -> None:
    s = Sample.model_validate(
        {
            "seq": 1042,
            "ts": 1761267012.345,
            "cycle_ms": 113.3,
            "source": "can_virtual",
            "values": {"rpm": {"pid": "0x0C", "value": 2000.25, "unit": "rpm", "rtt_ms": 11.2}},
            "errors": {"timeouts": 0, "invalid": 0},
        }
    )
    assert s.values["rpm"].value == 2000.25
    assert Sample.model_validate_json(s.model_dump_json()) == s


def test_dtc_report() -> None:
    r = DtcReport.model_validate(
        {
            "ts": 1.0,
            "mil": True,
            "count": 1,
            "codes": [{"code": "P0300", "description": "x", "status": "stored"}],
        }
    )
    assert r.codes[0].code == "P0300"


def test_stats() -> None:
    s = Stats.model_validate(
        {
            "received": 2104,
            "lost": 0,
            "duplicated": 0,
            "latency_ms": {"mean": 0.64, "p95": 0.89, "p99": 1.79, "max": 4.4},
            "update_rate_hz": 8.8,
        }
    )
    assert s.latency_ms.p99 == 1.79
