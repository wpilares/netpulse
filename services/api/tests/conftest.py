from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from netpulse_api.app import create_app


class StubProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable

    async def is_reachable(self) -> bool:
        return self.reachable


@pytest.fixture
def make_client() -> Callable[[bool | None], TestClient]:
    def factory(database_reachable: bool | None) -> TestClient:
        probe = None if database_reachable is None else StubProbe(reachable=database_reachable)
        return TestClient(create_app(database_probe=probe))

    return factory
