from football_txt_parser import normalize_score_line, parse_score_line, parse_all_results


SAMPLE_V = "Mon Jun 15  Mexico  v  France  3-1  @  Estadio Azteca"
SAMPLE_SCORE = "Brazil  2-0  Turkey  @  Ulsan Munsu Football Stadium"
SAMPLE_DATE = "Wed Jun 12  14:00 UTC-3  Argentina  2-1  Saudi Arabia  @  Lusail Stadium"


def test_normalize_strips_date():
    n = normalize_score_line(SAMPLE_DATE)
    assert "Argentina" in n
    assert "2-1" in n
    assert "@" in n


def test_parse_v_format():
    row = parse_score_line(SAMPLE_V)
    assert row is not None
    assert row["team1"] == "Mexico"
    assert row["team2"] == "France"
    assert row["score_home"] == 3
    assert row["score_away"] == 1


def test_parse_score_format():
    row = parse_score_line(SAMPLE_SCORE)
    assert row is not None
    assert row["team1"] == "Brazil"
    assert row["team2"] == "Turkey"


def test_parse_all_results_skips_headers():
    text = """
Group A | Team1 · Team2
Brazil  2-0  Turkey  @  Stadium A
Some header line without score
"""
    rows = parse_all_results(text)
    assert len(rows) == 1
    assert rows[0]["team1"] == "Brazil"
