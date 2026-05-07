import os

import pytest

from loom.runtimes.dify.v1_14.client import DifyClient

LIVE = os.environ.get("LOOM_DIFY_LIVE") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set LOOM_DIFY_LIVE=1 to run against pinned Dify")


def test_health():
    c = DifyClient(base_url="http://localhost:5001", api_key=os.environ["LOOM_DIFY_KEY"])
    assert c.health() is True
