import pytest

from xtpages.config import Config, ConfigError, SlotSpec, validate


def ok(cfg):
    validate(cfg)


def fails_with(cfg, needle):
    with pytest.raises(ConfigError) as exc:
        validate(cfg)
    assert needle in str(exc.value), str(exc.value)


def test_shipped_config_is_valid(cfg):
    ok(cfg)


def test_feed_must_be_known(cfg):
    cfg.content.feed = "spicy"
    fails_with(cfg, "content.feed")


@pytest.mark.parametrize("count", [0, 101])
def test_story_count_range(cfg, count):
    cfg.content.story_count = count
    fails_with(cfg, "content.story_count")


def test_candidate_pool_below_story_count(cfg):
    cfg.dedupe.candidate_pool = 5
    cfg.content.story_count = 20
    fails_with(cfg, "dedupe.candidate_pool")


def test_retention_days_floor(cfg):
    cfg.retention_days = 0
    fails_with(cfg, "retention_days")


@pytest.mark.parametrize("n", [0, 11])
def test_max_concurrency_range(cfg, n):
    cfg.fetch.max_concurrency = n
    fails_with(cfg, "fetch.max_concurrency")


def test_slots_required(cfg):
    cfg.slots = []
    fails_with(cfg, "schedule.slots")


def test_slot_label_shape(cfg):
    cfg.slots = [SlotSpec("0 3 * * *", "3am")]
    fails_with(cfg, "four digits")


def test_duplicate_slot_labels(cfg):
    cfg.slots = [SlotSpec("0 3 * * *", "0300"), SlotSpec("0 21 * * *", "0300")]
    fails_with(cfg, "duplicate labels")


def test_catalog_entry_cap(cfg):
    cfg.retention_days = 60  # 60 x 2 slots + 1 = 121, over the device's 62
    fails_with(cfg, "device's limit")


def test_entry_cap_counts_the_unpruned_issue(cfg):
    cfg.retention_days = 31  # 31 x 2 + 1 = 63, one over
    fails_with(cfg, "63 catalog entries")


@pytest.mark.parametrize("bad", ["", "x" * 41, "HN Dåily", "HN:Daily", "HN/Daily"])
def test_title_short_rules(cfg, bad):
    cfg.site.title_short = bad
    fails_with(cfg, "site.title_short")


def test_base_url_must_be_https(cfg):
    cfg.site.base_url = "http://example.com/"
    fails_with(cfg, "site.base_url")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/",
        "http://127.0.0.1:8000/",
        "http://192.168.1.42:8000/",
        "http://10.0.0.5/",
        "http://172.16.4.4:8000/",
    ],
)
def test_local_origins_exempt_from_https(cfg, url):
    cfg.site.base_url = url
    ok(cfg)


def test_base_url_from_github_repository(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "SomeOwner/xtpages")
    config = Config()
    assert config.base_url == "https://someowner.github.io/xtpages/"
    assert config.url_for("catalog.xml") == "https://someowner.github.io/xtpages/catalog.xml"


def test_base_url_localhost_fallback(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert Config().base_url == "http://localhost:8000/"


def test_explicit_base_url_gets_trailing_slash():
    config = Config()
    config.site.base_url = "https://example.com/sub"
    assert config.base_url == "https://example.com/sub/"


def test_impersonate_accepts_a_target_or_blank(cfg):
    cfg.fetch.impersonate = "chrome"
    ok(cfg)
    cfg.fetch.impersonate = ""
    ok(cfg)


def test_impersonate_rejects_junk(cfg):
    cfg.fetch.impersonate = "Chrome/141 (fake)"
    fails_with(cfg, "fetch.impersonate")
