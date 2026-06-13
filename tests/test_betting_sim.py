from betting_sim import (
    build_match_legs,
    classify_tier,
    select_curated_matches,
    settle_asian,
    settle_over_under,
    simulate_flat_bets,
)


def _pred(strength=0.15, ph=72, pd=18, pa=10, under=35):
    return {
        "prob_home": ph,
        "prob_draw": pd,
        "prob_away": pa,
        "prob_under_25": under,
        "strength_diff": strength,
        "asian_line_home": -1.0,
        "asian_handicap": "亚盘: 巴西-1.0",
        "home": {"elo": 1700, "name": "巴西"},
        "away": {"elo": 1400, "name": "弱队"},
        "actual_home": 2,
        "actual_away": 0,
        "played": True,
        "title": "巴西 vs 弱队",
    }


def test_classify_tier_strong():
    assert classify_tier(_pred(strength=0.15)) == "strong"


def test_classify_tier_medium():
    assert classify_tier(_pred(strength=0.08)) == "medium"


def test_strong_legs_three_bets():
    pred = _pred(strength=0.15, under=35)
    legs = build_match_legs(pred, "strong")
    types = [l["type"] for l in legs]
    assert types == ["1x2", "asian", "ou"]
    assert sum(l["stake"] for l in legs) == 150


def test_medium_legs_two_bets():
    pred = _pred(strength=0.08, under=40)
    legs = build_match_legs(pred, "medium")
    assert len(legs) == 2
    assert sum(l["stake"] for l in legs) == 100


def test_settle_asian_home_minus_one():
    assert settle_asian(2, 0, -1.0) == "win"
    assert settle_asian(1, 0, -1.0) == "push"
    assert settle_asian(1, 1, -1.0) == "lose"


def test_settle_over_under():
    assert settle_over_under(2, 1, "over") is True
    assert settle_over_under(1, 0, "under") is True


def test_select_curated_limits():
    preds = [_pred(strength=0.15 - i * 0.001, ph=70 - i) for i in range(15)]
    preds += [_pred(strength=0.08 - i * 0.001, ph=55 - i) for i in range(10)]
    picked = select_curated_matches(preds)
    assert len(picked) == 15


def test_simulate_flat_bets_profit_on_wins():
    preds = [_pred()]
    sim = simulate_flat_bets(preds, stake=50, bankroll_start=200, only_played=True)
    assert sim["bets"] == 1
    assert sim["wins"] == 1
    assert sim["profit"] > 0
