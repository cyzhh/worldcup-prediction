from predictor import _pred_outcome, pick_display_score


def test_pick_display_score_matches_highest_wdl_outcome():
    scores = [
        (0, 0, 0.20),
        (1, 0, 0.18),
        (1, 1, 0.16),
        (2, 0, 0.12),
        (0, 1, 0.10),
    ]
    # 主胜最高 → 应在主胜比分里选概率最高的 1:0
    h, a = pick_display_score(0.412, 0.360, 0.228, scores, 0.03)
    assert _pred_outcome(0.412, 0.360, 0.228) == "home"
    assert h > a
    assert (h, a) == (1, 0)


def test_pick_display_score_draw_picks_best_draw_score():
    scores = [
        (0, 0, 0.22),
        (1, 1, 0.18),
        (2, 2, 0.05),
        (1, 0, 0.15),
    ]
    h, a = pick_display_score(0.30, 0.38, 0.32, scores, 0.0)
    assert _pred_outcome(0.30, 0.38, 0.32) == "draw"
    assert h == a
    assert (h, a) == (0, 0)


def test_pick_display_score_away_win():
    scores = [
        (0, 1, 0.21),
        (1, 2, 0.14),
        (0, 2, 0.11),
        (1, 0, 0.10),
    ]
    h, a = pick_display_score(0.25, 0.30, 0.45, scores, -0.08)
    assert _pred_outcome(0.25, 0.30, 0.45) == "away"
    assert h < a
    assert (h, a) == (0, 1)
