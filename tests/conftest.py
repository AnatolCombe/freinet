import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-ref",
        action="store_true",
        help="réécrire les références du ticket (texte + empreinte PNG) au lieu de les comparer",
    )


@pytest.fixture
def update_ref(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-ref"))


@pytest.fixture(autouse=True)
def sans_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests n'appellent jamais le vrai LLM (inv. 7) ; `tests/matin/test_coach.py` le
    remplace par une commande factice. Ni le réseau (météo, `tests/general/test_meteo.py` le
    rétablit avec un faux téléchargeur)."""
    monkeypatch.setenv("FREINET_SANS_LLM", "1")
    monkeypatch.setenv("FREINET_SANS_RESEAU", "1")  # ni météo ni autre appel réseau
