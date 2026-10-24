import importlib

import obd

SUBPACOTES = ["protocol", "transport", "simulator", "collector", "server", "web"]


def test_pacote_obd_importa() -> None:
    assert obd.__name__ == "obd"


def test_subpacotes_existem_e_importam() -> None:
    for nome in SUBPACOTES:
        assert importlib.import_module(f"obd.{nome}").__name__ == f"obd.{nome}"
