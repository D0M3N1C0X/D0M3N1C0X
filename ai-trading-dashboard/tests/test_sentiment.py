from backend.sentiment import score_text


def test_positive_negative_neutral():
    assert score_text("Nvidia beats estimates, raises guidance")["label"] == "positivo"
    assert score_text("AMD plunges after analyst downgrade")["label"] == "negativo"
    assert score_text("Company to present at conference")["label"] == "neutro"


def test_negation_flips():
    assert score_text("Micron does not miss estimates")["score"] > 0
