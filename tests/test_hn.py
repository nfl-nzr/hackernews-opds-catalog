import httpx
import pytest

from conftest import fixture_json, make_client
from xtpages import hn


def router(items):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("stories.json"):
            return httpx.Response(200, json=list(items))
        item_id = int(path.split("/")[-1].removesuffix(".json"))
        return httpx.Response(200, json=items[item_id])

    return handler


def test_fetch_story_ids_respects_limit(cfg):
    ids = fixture_json("hn_topstories.json")
    client = make_client(lambda r: httpx.Response(200, json=ids))
    assert hn.fetch_story_ids(cfg, 3, client) == ids[:3]


def test_story_parsed(cfg):
    item = fixture_json("hn_item_story.json")
    client = make_client(lambda r: httpx.Response(200, json=item))
    story = hn.fetch_story(cfg, item["id"], client)
    assert story.title == "A thing someone built"
    assert story.domain == "example.com"
    assert story.is_self_post is False
    assert story.hn_url == "https://news.ycombinator.com/item?id=45123456"
    assert story.link == "https://example.com/a-thing"


def test_self_post_detected_by_missing_url(cfg):
    item = fixture_json("hn_item_selfpost.json")
    client = make_client(lambda r: httpx.Response(200, json=item))
    story = hn.fetch_story(cfg, item["id"], client)
    assert story.is_self_post is True
    assert story.domain == "news.ycombinator.com"
    assert story.link == story.hn_url
    assert "<pre>" in story.text


@pytest.mark.parametrize("flag", ["deleted", "dead"])
def test_deleted_and_dead_dropped(cfg, flag):
    item = {**fixture_json("hn_item_story.json"), flag: True}
    client = make_client(lambda r: httpx.Response(200, json=item))
    assert hn.fetch_story(cfg, item["id"], client) is None


def test_non_story_dropped(cfg):
    item = {**fixture_json("hn_item_story.json"), "type": "job"}
    client = make_client(lambda r: httpx.Response(200, json=item))
    assert hn.fetch_story(cfg, item["id"], client) is None


def test_min_score_filter(cfg):
    cfg.content.min_score = 500
    item = fixture_json("hn_item_story.json")  # score 412
    client = make_client(lambda r: httpx.Response(200, json=item))
    assert hn.fetch_story(cfg, item["id"], client) is None


def test_fetch_stories_preserves_input_order(cfg, monkeypatch):
    base = fixture_json("hn_item_story.json")
    ids = [5, 3, 9, 1]
    items = {i: {**base, "id": i, "title": f"story {i}"} for i in ids}
    monkeypatch.setattr(hn, "_client", lambda c: make_client(router(items)))
    assert [s.id for s in hn.fetch_stories(cfg, ids)] == ids


def test_fetch_stories_drops_unusable_but_keeps_order(cfg, monkeypatch):
    base = fixture_json("hn_item_story.json")
    ids = [5, 3, 9]
    items = {5: {**base, "id": 5}, 3: {**base, "id": 3, "dead": True}, 9: {**base, "id": 9}}
    monkeypatch.setattr(hn, "_client", lambda c: make_client(router(items)))
    assert [s.id for s in hn.fetch_stories(cfg, ids)] == [5, 9]
