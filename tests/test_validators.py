from validators import validate_elo, validate_probabilities


def test_validate_probabilities_ok():
    assert validate_probabilities(40, 30, 30) == []


def test_validate_probabilities_bad_sum():
    issues = validate_probabilities(50, 30, 30)
    assert any("概率和" in i for i in issues)


def test_validate_elo_range():
    assert validate_elo(1500) == []
    assert validate_elo(900)
