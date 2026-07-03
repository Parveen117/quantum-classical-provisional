from quantum_native_bridge_pro.expected_models import (
    bell_model,
    classify_gap,
    evaluate_expected_model,
    ghz_model,
    l1_gap,
    model_from_template,
    normalize_distribution,
    single_qubit_bias_model,
)


def test_bell_model_recognizes_bell_counts():
    model = bell_model(tolerance=0.08)
    result = evaluate_expected_model(model, {"00": 506, "01": 11, "10": 9, "11": 498})
    assert result["classification"] == "RECOGNITION"
    assert result["recognized"] is True
    assert result["distribution_gap"] < 0.08


def test_bell_model_detects_wrong_counts():
    model = bell_model(tolerance=0.08)
    result = evaluate_expected_model(model, {"00": 250, "01": 250, "10": 250, "11": 274})
    assert result["classification"] == "ACTIONABLE_RESIDUE"


def test_ghz_model():
    model = ghz_model(3, tolerance=0.10)
    result = evaluate_expected_model(model, {"000": 510, "111": 514})
    assert result["classification"] == "RECOGNITION"


def test_single_qubit_bias_model():
    model = single_qubit_bias_model(0.7, tolerance=0.10)
    result = evaluate_expected_model(model, {"0": 700, "1": 324})
    assert result["classification"] == "RECOGNITION"


def test_model_from_template_custom():
    model = model_from_template({
        "distribution": {"0": 3, "1": 1},
        "tolerance": 0.05,
        "model_id": "custom-test",
    })
    assert model.model_id == "custom-test"
    assert model.distribution["0"] == 0.75


def test_gap_classification_bands():
    assert classify_gap(0.01, 0.10) == "RECOGNITION"
    assert classify_gap(0.15, 0.10) == "BOUNDED_RESIDUE"
    assert classify_gap(0.25, 0.10) == "ACTIONABLE_RESIDUE"


def test_normalize_distribution():
    assert normalize_distribution({"a": 1, "b": 3}) == {"a": 0.25, "b": 0.75}
    assert l1_gap({"a": 1.0}, {"a": 10}) == 0.0
