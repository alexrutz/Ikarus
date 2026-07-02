import pytest

from ikarus.core.simloop import Sim


@pytest.fixture
def sim() -> Sim:
    """Full sim stack (no HTTP server), cruise situation, fast-time."""
    return Sim(situation="cruise")


@pytest.fixture
def sim_runway() -> Sim:
    return Sim(situation="runway")
