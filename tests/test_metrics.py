from metrics import classification_summary, macro_f1, per_class_prf, upset_capture_rate


def _pred(h, d, a, elo_h=1600, elo_a=1500, ah=1, aa=0):
    return {
        "prob_home": h,
        "prob_draw": d,
        "prob_away": a,
        "home": {"elo": elo_h},
        "away": {"elo": elo_a},
        "actual_home": ah,
        "actual_away": aa,
    }


def test_perfect_predictions():
    preds = [
        _pred(70, 20, 10, ah=2, aa=0),
        _pred(10, 20, 70, elo_h=1400, elo_a=1600, ah=0, aa=1),
        _pred(20, 60, 20, ah=1, aa=1),
    ]
    summary = classification_summary(preds)
    assert summary["macro_f1"] == 1.0
    assert summary["draw_f1"] == 1.0


def test_macro_f1_from_per_class():
    per = per_class_prf(
        ["home", "draw", "away"],
        ["home", "home", "away"],
    )
    assert macro_f1(per) < 1.0
    assert per["draw"]["precision"] == 0.0


def test_upset_capture():
    preds = [
        _pred(10, 20, 70, elo_h=1700, elo_a=1500, ah=0, aa=2),
        _pred(70, 20, 10, elo_h=1700, elo_a=1500, ah=2, aa=0),
    ]
    upset = upset_capture_rate(preds, threshold=100.0)
    assert upset["upset_matches"] == 1
    assert upset["upset_captured"] == 1
    assert upset["upset_capture_rate"] == 1.0
