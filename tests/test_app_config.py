from app_config import load_app_config, model_defaults, sync_config


def test_config_loads():
    cfg = load_app_config()
    assert "paths" in cfg
    assert "sync" in cfg
    assert "model" in cfg


def test_live_refresh_is_list():
    sc = sync_config()
    live = sc.get("live_refresh") or []
    assert isinstance(live, list)
    assert "2026/worldcup.json" in live


def test_sync_sources_non_empty():
    sc = sync_config()
    sources = sc.get("sources") or {}
    assert len(sources) >= 10
    assert "2026/worldcup.json" in sources


def test_model_defaults_merge():
    defaults = model_defaults()
    assert 0.0 < defaults.get("group_stage_draw_base", 0) < 1.0
    assert defaults.get("draw_mass_blend") is not None
