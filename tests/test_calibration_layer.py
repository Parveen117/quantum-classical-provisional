from quantum_native_bridge_pro.calibration import CalibrationProfile, apply_readout_floor, build_calibrated_observation, normalize_counts


def test_count_normalization_basic():
    result = normalize_counts({"zero": 1, "one": 3})
    assert result["zero"] == 0.25
    assert result["one"] == 0.75


def test_readout_weighting_basic():
    profile = CalibrationProfile(
        profile_id="profile-demo",
        backend="demo-backend",
        readout_fidelity={"a": 0.9, "b": 1.0, "default": 0.95},
    )
    corrected = apply_readout_floor({"a": 50, "b": 50}, profile)
    assert set(corrected.keys()) == {"a", "b"}
    assert abs(sum(corrected.values()) - 1.0) < 1e-12


def test_calibrated_observation_evidence():
    profile = CalibrationProfile(
        profile_id="profile-demo",
        backend="demo-backend",
        readout_fidelity={"zero": 0.98, "one": 0.94},
    )
    corrected, evidence = build_calibrated_observation({"zero": 60, "one": 40}, profile)
    assert abs(sum(corrected.values()) - 1.0) < 1e-12
    assert evidence["calibration_profile_id"] == "profile-demo"
    assert evidence["correction_method"] == "readout_fidelity_weighting"
