from model_config import ModelConfig
from predictor import compute_draw_probability, get_blend_weights


def _team(form_w=3, form_d=2, style="传控"):
    return {
        "form": {"wins": form_w, "draws": form_d, "losses": 2, "xg_diff": 0.0, "goals_for": 1.5, "goals_against": 1.0},
        "tactics": {"style": style, "efficiency": 0.6},
    }


def test_draw_probability_higher_when_close():
    cfg = ModelConfig()
    close = compute_draw_probability(0.03, 30, 1, _team(), _team(), None, cfg)
    far = compute_draw_probability(0.20, 250, 1, _team(), _team(), None, cfg)
    assert close > far


def test_blend_weights_even_match_favors_poisson():
    cfg = ModelConfig()
    elo_w, poisson_w = get_blend_weights(0.03, 1, 25, cfg)
    assert poisson_w > elo_w
