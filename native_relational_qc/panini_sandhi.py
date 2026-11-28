"""Reversible vowel sandhi and a one-iteration search over its source pairs."""
import argparse
import json
import unicodedata
from fractions import Fraction
from itertools import product
from pathlib import Path

from .compact import CompactCircuit
from .exact import ONE
from .openqasm import dumps
from .reversible_logic import BooleanMap, compile_oracle


VOWELS = ("i", "ī", "u", "ū")
PAIRS = tuple(product(VOWELS, repeat=2))
# q6 chooses the rule, q5 the right family and q4 the surviving right length.
SURFACE_CODES = {"ī": 0, "ū": 2, "vi": 4, "vī": 5, "yu": 6, "yū": 7}
DEVANAGARI = {"इ": "i", "ई": "ī", "उ": "u", "ऊ": "ū",
              "वि": "vi", "वी": "vī", "यु": "yu", "यू": "yū"}


def _token(text):
    text = unicodedata.normalize("NFC", text)
    return DEVANAGARI.get(text, text)


def _surface(left, right):
    """Unaccented junction in continuous speech, restricted to PAIRS."""
    left_is_i = left in ("i", "ī")
    right_is_i = right in ("i", "ī")
    if left_is_i == right_is_i:
        return "ī" if left_is_i else "ū"
    return ("y" if left_is_i else "v") + right


def sandhi_oracle():
    """Compile |pair, y> → |pair, y XOR surface(pair)> for every target word y."""
    table = tuple(SURFACE_CODES[_surface(left, right)] for left, right in PAIRS)
    return compile_oracle(BooleanMap(4, 3, table))


def join(left, right):
    pair = (_token(left), _token(right))
    if pair not in PAIRS:
        raise ValueError("the two input vowels must belong to i, ī, u, ū")
    word = PAIRS.index(pair)
    oracle = sandhi_oracle()
    circuit = CompactCircuit(oracle.circuit.n_qubits)
    for bit, wire in enumerate(oracle.inputs):
        if word & (1 << bit):
            circuit.add("x", wire)
    oracle.append_to(circuit)
    state = circuit.state()
    for surface, code in SURFACE_CODES.items():
        # An exact unit amplitude checks both the output and the retained input.
        if state.amplitude(word | (code << len(oracle.inputs))) == ONE:
            return circuit, {"source_pair": pair, "surface": surface,
                             "rule": "6.1.101" if code < 4 else "6.1.77"}
    raise ArithmeticError("sandhi failed to preserve the source and produce a valid surface")


def search_circuit(surface):
    """Mark the computed surface, erase it coherently and diffuse the 16 inputs."""
    surface = _token(surface)
    if surface not in SURFACE_CODES:
        raise ValueError("unsupported sandhi surface")
    code = SURFACE_CODES[surface]
    oracle = sandhi_oracle()
    source, output = oracle.inputs, oracle.outputs
    circuit = CompactCircuit(oracle.circuit.n_qubits)
    for wire in source:
        circuit.add("h", wire)
    oracle.append_to(circuit)

    # Change the sign of the requested three-bit surface with a controlled CZ.
    zeros = [wire for bit, wire in enumerate(output) if (code >> bit) & 1 == 0]
    for wire in zeros:
        circuit.add("x", wire)
    circuit.add("h", output[2]).add("ccx", *output).add("h", output[2])
    for wire in zeros:
        circuit.add("x", wire)
    oracle.append_to(circuit, inverse=True)

    # I - 2|s><s|. The surface register is clean and supplies the temporary AND.
    for wire in source:
        circuit.add("h", wire).add("x", wire)
    scratch = output[0]
    circuit.add("ccx", source[0], source[1], scratch)
    circuit.add("h", source[3])
    circuit.add("ccx", scratch, source[2], source[3])
    circuit.add("h", source[3])
    circuit.add("ccx", source[0], source[1], scratch)
    for wire in source:
        circuit.add("x", wire).add("h", wire)
    return circuit


def search(surface):
    surface = _token(surface)
    circuit = search_circuit(surface)
    state = circuit.state()
    # The first four wires retain the source word. All higher wires must be clean
    # before their zero branch can be used as the full source distribution.
    if state.probability(dict.fromkeys(range(4, circuit.n_qubits), 0)) != ONE:
        raise ArithmeticError("search left information in the surface register")
    candidates = []
    hits = Fraction(0)
    for word, (left, right) in enumerate(PAIRS):
        probability = state.amplitude(word).norm2()
        if any(probability.coefficients[1:]):
            raise ArithmeticError("this one-iteration distribution must be rational")
        matches = _surface(left, right) == surface
        if matches:
            hits += probability.a
        candidates.append({"left": left, "right": right, "matches": matches,
                           "probability": str(probability.a)})
    prior = Fraction(sum(row["matches"] for row in candidates), len(PAIRS))
    return circuit, {"surface": surface, "grover_iterations": 1, "candidates": candidates,
                     "uniform_matching_probability": str(prior), "matching_probability": str(hits),
                     "clean_workspace_probability": "1"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nrqc panini-sandhi", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    forward = actions.add_parser("join", help="join two vowels and retain both inputs")
    for position in ("left", "right"):
        forward.add_argument(position, type=_token, choices=VOWELS)
    reverse = actions.add_parser("search", help="amplify the source pairs for a visible form")
    reverse.add_argument("surface", type=_token, choices=SURFACE_CODES)
    for action in (forward, reverse):
        action.add_argument("--qasm", type=Path, help="write the unmeasured circuit as OpenQASM")
    args = parser.parse_args(argv)
    if args.action == "join":
        circuit, result = join(args.left, args.right)
    else:
        circuit, result = search(args.surface)
    if args.qasm:
        args.qasm.write_text(dumps(circuit), encoding="utf-8")
    result.update(evidence_class="LOCAL_EXACT_CIRCUIT", hardware_job_id=None,
                  qubits=circuit.n_qubits, gates=len(circuit.operations))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0
