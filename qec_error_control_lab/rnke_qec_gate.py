"""RNKE-Q gate: recognition-kernel binding over the QEC error-control lab.

Turns the Shor-code pipeline into a fail-closed recognition cycle with typed
verdicts and a hash-chained receipt ledger, in the same grammar used by the
quantum Fredholm recognition-kernel engine (ACCEPT / CORRECT / REJECT) and the
SETU recognition layer (COMMITTED / REFUTED / CUT / DEFERRED).

Cycle (notational index n, not physical time):

    state_n --E--> candidate --R--> syndrome reports --audit--> residue
           --classify--> verdict --action--> state_{n+1} --receipt--> ledger

Verdicts (typed, exhaustive):
    COMMITTED   : residue zero; state enters recognized set unchanged.
    CORRECTED   : bounded residue (weight <= 1); correction applied, and the
                  post-correction residue is re-audited and must be zero.
    DEFERRED    : syndrome reports disagree (no strict majority) — held, no
                  state change, re-extraction requested.
    CUT         : residue outside the declared recovery model (weight > 1,
                  ambiguous multi-block syndrome, or fidelity not restored) —
                  fail-closed, state rejected for reinitialisation.

Nothing becomes state_{n+1} merely because it arrived: CORRECTED requires the
post-correction audit to be exact; otherwise the verdict is CUT.

Claim boundary: exact statevector level under the lab's declared single-Pauli
error model. Not a fault-tolerance, threshold, or hardware claim.

Dependency-free (stdlib only). Deterministic. Certificate SHA-256 bound.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

from qec_shor import (
    IncompleteSyndrome,
    apply_errors,
    encode_shor,
    extract_shor_syndrome,
    fidelity,
    majority_shor_syndrome,
    normalize_errors,
    recover_shor,
)

PROTOCOL = "rnke-qec-shor-gate-v1"
GENESIS = "0" * 64

COMMITTED = "COMMITTED"
CORRECTED = "CORRECTED"
DEFERRED = "DEFERRED"
CUT = "CUT"
VERDICTS = (COMMITTED, CORRECTED, DEFERRED, CUT)


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_root(state: Sequence[complex]) -> str:
    """Hash of the statevector rounded to 12 decimals (exact-arith lab states)."""
    rows = [[round(c.real, 12) + 0.0, round(c.imag, 12) + 0.0] for c in state]
    return sha256_hex(canonical_json(rows))


@dataclass(frozen=True)
class Residue:
    """Typed open residue after the lawful recovery model is subtracted."""
    syndrome: tuple[int, ...] | None
    weight_bound: int | None          # 0, 1, or None (outside model)
    bit_blocks_active: int
    phase_block_active: bool
    note: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Receipt:
    protocol: str
    index_n: int
    parent_receipt_hash: str
    input_root: str
    syndrome_reports: list[list[int]]
    residue: dict[str, object]
    verdict: str
    corrections: list[dict[str, object]]
    output_root: str | None
    fidelity_to_reference: float | None
    receipt_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_residue(syndrome: Sequence[int] | None) -> Residue:
    if syndrome is None:
        return Residue(None, None, 0, False, "no majority syndrome")
    from qec_shor import PAIR_TO_OFFSET, PAIR_TO_BLOCK  # local, declared tables

    bit_blocks = 0
    for block in range(3):
        if PAIR_TO_OFFSET[(syndrome[2 * block], syndrome[2 * block + 1])] is not None:
            bit_blocks += 1
    phase = PAIR_TO_BLOCK[(syndrome[6], syndrome[7])] is not None
    if bit_blocks > 1:
        return Residue(tuple(syndrome), None, bit_blocks, phase,
                       "multi-block bit-flip activation: outside single-Pauli model")
    weight = 0 if (bit_blocks == 0 and not phase) else 1
    return Residue(tuple(syndrome), weight, bit_blocks, phase,
                   "zero residue" if weight == 0 else "weight<=1 residue, recoverable")


def recognition_cycle(
    *,
    index_n: int,
    parent_receipt_hash: str,
    reference_state: Sequence[complex],
    candidate_state: Sequence[complex],
    syndrome_reports: Sequence[Sequence[int]],
) -> tuple[tuple[complex, ...], Receipt]:
    """One fail-closed recognition cycle. Returns (state_{n+1}, receipt)."""
    input_root = state_root(candidate_state)
    reports = [list(r) for r in syndrome_reports]

    # R: majority over repeated reports (DEFERRED if no strict majority)
    try:
        used = majority_shor_syndrome(syndrome_reports)
    except IncompleteSyndrome:
        residue = audit_residue(None)
        verdict, corrections, out_state, out_root, fid = DEFERRED, (), None, None, None
        return _finish(candidate_state, index_n, parent_receipt_hash, input_root,
                       reports, residue, verdict, corrections, out_root, fid)

    residue = audit_residue(used)
    if residue.weight_bound is None:
        return _finish(candidate_state, index_n, parent_receipt_hash, input_root,
                       reports, residue, CUT, (), None, None)

    if residue.weight_bound == 0:
        fid = fidelity(candidate_state, reference_state)
        verdict = COMMITTED if fid == 1.0 else CUT
        out_root = state_root(candidate_state) if verdict == COMMITTED else None
        return _finish(candidate_state, index_n, parent_receipt_hash, input_root,
                       reports, residue, verdict, (), out_root, fid)

    # weight 1: apply correction, then RE-AUDIT (post-correction residue must be 0)
    try:
        corrected, corrections = recover_shor(candidate_state, used)
    except IncompleteSyndrome:
        return _finish(candidate_state, index_n, parent_receipt_hash, input_root,
                       reports, residue, CUT, (), None, None)
    post = audit_residue(extract_shor_syndrome(corrected))
    fid = fidelity(corrected, reference_state)
    if post.weight_bound == 0 and fid == 1.0:
        return _finish(corrected, index_n, parent_receipt_hash, input_root,
                       reports, residue, CORRECTED, corrections, state_root(corrected), fid)
    return _finish(candidate_state, index_n, parent_receipt_hash, input_root,
                   reports, residue, CUT, corrections, None, fid)


def _finish(state, index_n, parent, input_root, reports, residue, verdict,
            corrections, out_root, fid):
    body = {
        "protocol": PROTOCOL,
        "index_n": index_n,
        "parent_receipt_hash": parent,
        "input_root": input_root,
        "syndrome_reports": reports,
        "residue": residue.to_dict(),
        "verdict": verdict,
        "corrections": [{"qubit": q, "pauli": p} for q, p in corrections],
        "output_root": out_root,
        "fidelity_to_reference": fid,
    }
    receipt = Receipt(**body, receipt_hash=sha256_hex(canonical_json(body)))
    # state only advances on COMMITTED / CORRECTED
    next_state = tuple(state) if verdict in (COMMITTED, CORRECTED) else None
    return next_state, receipt


# ----------------------------------------------------------------------------
# Campaign: exhaustive single-Pauli + controls, receipt chain, certificate
# ----------------------------------------------------------------------------

def _named_states() -> dict[str, tuple[complex, complex]]:
    s = 2 ** -0.5
    return {"zero": (1, 0), "one": (0, 1), "plus": (s, s), "imag": (s, 1j * s)}


def build_rnke_qec_certificate() -> dict[str, object]:
    ledger: list[dict[str, object]] = []
    parent = GENESIS
    n = 0
    tallies = {v: 0 for v in VERDICTS}
    checks = {
        "every_clean_state_committed": True,
        "every_single_pauli_corrected": True,
        "every_two_error_cut_or_corrected_never_committed": True,
        "disagreeing_reports_deferred": True,
        "chain_intact": True,
    }

    def step(reference, candidate, reports):
        nonlocal parent, n
        nxt, r = recognition_cycle(index_n=n, parent_receipt_hash=parent,
                                   reference_state=reference, candidate_state=candidate,
                                   syndrome_reports=reports)
        ledger.append(r.to_dict())
        parent = r.receipt_hash
        n += 1
        tallies[r.verdict] += 1
        return nxt, r

    for name, (a, b) in _named_states().items():
        ref = encode_shor(a, b)
        # clean
        s = extract_shor_syndrome(ref)
        _, r = step(ref, ref, [s, s, s])
        checks["every_clean_state_committed"] &= r.verdict == COMMITTED
        # all 27 single Paulis
        for q in range(9):
            for p in "XYZ":
                cand = apply_errors(ref, [(q, p)])
                s = extract_shor_syndrome(cand)
                _, r = step(ref, cand, [s, s, s])
                checks["every_single_pauli_corrected"] &= r.verdict == CORRECTED
        # two-error negative controls (must never be COMMITTED)
        for errs in ([(0, "X"), (3, "X")], [(0, "X"), (1, "X")], [(0, "Z"), (4, "Z")]):
            cand = apply_errors(ref, errs)
            s = extract_shor_syndrome(cand)
            _, r = step(ref, cand, [s, s, s])
            checks["every_two_error_cut_or_corrected_never_committed"] &= r.verdict != COMMITTED
        # disagreeing reports -> DEFERRED
        cand = apply_errors(ref, [(2, "X")])
        s = list(extract_shor_syndrome(cand))
        s2 = s.copy(); s2[0] ^= 1
        s3 = s.copy(); s3[1] ^= 1
        _, r = step(ref, cand, [s, s2, s3])
        checks["disagreeing_reports_deferred"] &= r.verdict == DEFERRED

    # verify chain
    prev = GENESIS
    for entry in ledger:
        body = {k: v for k, v in entry.items() if k != "receipt_hash"}
        ok = entry["parent_receipt_hash"] == prev and sha256_hex(canonical_json(body)) == entry["receipt_hash"]
        checks["chain_intact"] &= ok
        prev = entry["receipt_hash"]

    body = {
        "protocol": PROTOCOL,
        "claim_boundary": (
            "Exact statevector, declared single-Pauli error model, repeated-syndrome "
            "majority. Recognition-kernel binding (typed verdict, re-audited correction, "
            "hash-chained receipts). Not fault tolerance, not a threshold, not hardware."
        ),
        "verdict_tallies": tallies,
        "cycles": n,
        "checks": checks,
        "classification": "PASS_RNKE_QEC_GATE_V1" if all(checks.values()) else "FAIL_RNKE_QEC_GATE_V1",
        "ledger_head": parent,
        "ledger": ledger,
    }
    body["certificate_sha256"] = sha256_hex(canonical_json(body))
    return body


if __name__ == "__main__":
    import argparse, pathlib
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="generated/rnke_qec_gate_certificate.json")
    a = ap.parse_args()
    cert = build_rnke_qec_certificate()
    pathlib.Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.output).write_text(canonical_json(cert) + "\n")
    print(json.dumps({k: cert[k] for k in ("classification", "verdict_tallies", "cycles", "checks", "ledger_head", "certificate_sha256")}, indent=2))
