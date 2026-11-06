from __future__ import annotations

import io

from zsynctech_studio_sdk import get_logger
from zsynctech_studio_sdk.loggers import configure_logging, logger


def test_the_sdk_lines_name_the_sdk() -> None:
    out = io.StringIO()
    configure_logging(sink=out)

    logger.info("conectado")

    assert "| INFO     | zsynctech-studio-sdk - conectado" in out.getvalue()


def test_a_script_logs_in_the_same_format_under_its_own_name() -> None:
    out = io.StringIO()
    configure_logging(sink=out)

    get_logger("meu-robo").success("boleto baixado")

    assert "| SUCCESS  | meu-robo - boleto baixado" in out.getvalue()


def test_the_level_applies_to_the_script_lines_too() -> None:
    out = io.StringIO()
    configure_logging(level="WARNING", sink=out)

    get_logger("meu-robo").info("detalhe")
    get_logger("meu-robo").warning("sem oferta")

    assert "detalhe" not in out.getvalue()
    assert "sem oferta" in out.getvalue()
