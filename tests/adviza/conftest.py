from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.adviza.scenario import Site, arreter, demarrer, racine_deux_eleves


@pytest.fixture
def site(tmp_path: Path) -> Iterator[Site]:
    racine = tmp_path / "r"
    ids = racine_deux_eleves(racine)
    instance = demarrer(racine, ids)
    try:
        yield instance, racine, ids
    finally:
        arreter(instance)
