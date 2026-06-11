import importlib

import pytest

from backend.core.services.runner import (
    EON_DOWNLOADER,
    HBO_DOWNLOADER,
    HRTI_BROWSER,
    HRTI_DOWNLOADER,
    RTS_DOWNLOADER,
    VOYO_DOWNLOADER,
    SKYSHOWTIME_DOWNLOADER,
)


@pytest.mark.parametrize(
    "module",
    [
        VOYO_DOWNLOADER,
        HRTI_DOWNLOADER,
        HRTI_BROWSER,
        EON_DOWNLOADER,
        RTS_DOWNLOADER,
        HBO_DOWNLOADER,
        SKYSHOWTIME_DOWNLOADER,
    ],
)
def test_service_modules_import(module: str):
    mod = importlib.import_module(module)
    assert mod is not None
