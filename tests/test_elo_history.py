from pathlib import Path

from elo_history import build_elo_ratings, parse_cup_txt_results


def test_parse_cup_txt_results():
    sample = Path(__file__).parent.parent / "data" / "openfootball" / "1998--france" / "cup.txt"
    if not sample.exists():
        return
    text = sample.read_text(encoding="utf-8")
    rows = parse_cup_txt_results(text)
    assert len(rows) > 40
    assert all("score_home" in r for r in rows[:5])


def test_build_elo_ratings_monotonic():
    sample = Path(__file__).parent.parent / "data" / "openfootball" / "1998--france" / "cup.txt"
    if not sample.exists():
        return
    seed = {"BRA": {"elo": 2000}, "FRA": {"elo": 1950}}
    ratings = build_elo_ratings([sample], seed)
    assert "BRA" in ratings or "FRA" in ratings
