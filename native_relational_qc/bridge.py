"""Circuit-derived predictions for the existing recognition evidence pipeline."""
import math
from .circuit import Circuit


def expected_model(circuit: Circuit, *, tolerance: float):
    """Derive an ExpectedModel from a circuit; choose tolerance before observing data.

    This creates a prediction, never a hardware or physical-validation certificate.
    """
    from quantum_native_bridge_pro.expected_models import ExpectedModel
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise ValueError("TVD tolerance must be a finite number in [0, 1]")
    return ExpectedModel(
        model_id="native-relational-" + circuit.digest(),
        model_type="native_relational_ideal_unitary_v1",
        distribution=circuit.probabilities(), tolerance=tolerance,
        metadata={"circuit_sha256": circuit.digest(), "evidence_class": "MODEL_PREDICTION",
                  "bit_order": circuit.to_dict()["bit_order"],
                  "measurement_map": list(circuit.measurements),
                  "hardware_job_id": None, "metric": "total_variation_distance"},
    )
