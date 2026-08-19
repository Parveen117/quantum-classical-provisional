"""Keep root-level hardware entry points out of test collection.

Several scripts at the repository root are IBM Quantum submission tools; they
exit at import time when qiskit-ibm-runtime is absent, which aborts collection
in environments (including CI) that install only pytest. Their logic is covered
by the dedicated test modules.
"""
collect_ignore_glob = [
    "run_multi_ledger_operator_memory_test.py",
    "run_multi_ledger_replication_job.py",
    "run_operator_controlled_memory_transistor_test.py",
    "run_ugd_seam_ledger_test.py",
    "export_multi_ledger_device_evidence.py",
    "evaluate_multi_ledger_replication.py",
    "quantum_fredholm_recognition_kernel_engine.py",
    "qec_error_control_lab/coherence_lab/ibm_dd_hardware.py",
    "qec_error_control_lab/ibm_shor_3round_hardware.py",
    "qec_error_control_lab/capture_ibm_calibration_snapshot.py",
]
