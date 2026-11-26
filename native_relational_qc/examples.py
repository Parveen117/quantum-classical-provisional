"""Small native programs; every expected answer has an analytic derivation."""
from .algebra import R, K
from .circuit import Circuit


def bell(basis="ZZ"):
    if len(basis) != 2 or any(letter not in "XYZ" for letter in basis):
        raise ValueError("basis must contain two X/Y/Z labels, ordered q0 then q1")
    out = Circuit(2).add("h", 0).add("cx", 0, 1)
    for q, letter in enumerate(basis):
        if letter == "Y":
            out.add("sdg", q).add("h", q)
        elif letter == "X":
            out.add("h", q)
    return out.measure_all()


def ghz(n=3):
    out = Circuit(n).add("h", 0)
    for q in range(1, n):
        out.add("cx", 0, q)
    return out.measure_all()


def bernstein_vazirani(secret="1011"):
    """Return the secret in high-to-low bit order using a phase oracle."""
    if not secret or any(bit not in "01" for bit in secret):
        raise ValueError("secret must be a nonempty binary string")
    out = Circuit(len(secret))
    for q in range(len(secret)):
        out.add("h", q)
    for q, bit in enumerate(reversed(secret)):
        if bit == "1":
            out.add("z", q)
    for q in range(len(secret)):
        out.add("h", q)
    return out.measure_all()


def grover_search(marked):
    """One Grover iteration on four items; labels are printed q1 q0."""
    if marked not in ("00", "01", "10", "11"):
        raise ValueError("expected a two-bit marked item")
    out = Circuit(2).add("h", 0).add("h", 1)
    zero_bits = [q for q, bit in enumerate(reversed(marked)) if bit == "0"]
    for q in zero_bits:
        out.add("x", q)
    out.add("cz", 0, 1)
    for q in zero_bits:
        out.add("x", q)
    out.add("h", 0).add("h", 1).add("x", 0).add("x", 1)
    out.add("cz", 0, 1).add("x", 0).add("x", 1).add("h", 0).add("h", 1)
    return out.measure_all()


def grover_11():
    return grover_search("11")


def order_memory(erase=False):
    """Relative RK/KR phase is read by a coherent control (q0)."""
    # (RK)^dagger KR = -I; erase replaces KR by RK and yields I.
    first, second = R @ K, R @ K if erase else K @ R
    return (Circuit(2).add("h", 0)
            .control(first.conj().T @ second, 0, 1)
            .add("h", 0).measure_all())
