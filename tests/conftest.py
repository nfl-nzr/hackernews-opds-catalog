from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from xtpages.config import Config, SlotSpec
from xtpages.models import Article, Status, Story

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str):
    return json.loads(fixture(name))


@pytest.fixture
def cfg() -> Config:
    config = Config()
    config.slots = [SlotSpec("0 3 * * *", "0300"), SlotSpec("0 21 * * *", "2100")]
    config.site.base_url = "https://owner.github.io/repo/"
    return config


@pytest.fixture
def story() -> Story:
    return Story(
        id=45123456,
        title="A thing someone built",
        url="https://example.com/a-thing",
        score=412,
        by="someuser",
        time=1788657600,
    )


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def html_response(body: str, status: int = 200, ctype: str = "text/html"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    return handler


def article(story: Story, status: Status = Status.OK, body: str = "<p>text</p>") -> Article:
    return Article(story=story, status=status, body_html=body, chars=len(body))


NOW = datetime(2026, 9, 6, 3, 7, 41, tzinfo=UTC)
