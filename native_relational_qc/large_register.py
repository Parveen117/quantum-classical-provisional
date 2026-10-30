"""Iterative circuit description for explicitly selected large-register engines."""
from .compact import CompactCircuit, _integer

DEFAULT_REGISTER_BOUND = 2056
REGISTER_BOUND_CEILING = 1 << 22
MAX_LARGE_QUBITS = DEFAULT_REGISTER_BOUND


def register_bound():
    """The declared register bound in force; 2056 is a default, not a limit."""
    return MAX_LARGE_QUBITS


def declare_register_bound(n_qubits):
    """Declare a new register bound for the large-register engines.

    The bound is a resource declaration read at compile time by the Pauli,
    Clifford+T and Clifford-frame engines. Returns the previous bound. The
    ceiling keeps Pauli bit words and plans finite; it is not a hardware claim.
    """
    global MAX_LARGE_QUBITS
    previous = MAX_LARGE_QUBITS
    MAX_LARGE_QUBITS = _integer(n_qubits, 'register bound', 1, REGISTER_BOUND_CEILING)
    return previous


class LargeCircuit(CompactCircuit):
    """Named circuit IR only; it does not allocate a recursive state graph."""
    def __init__(self, n_qubits):
        self.n_qubits = _integer(n_qubits, 'qubits', 1, register_bound())
        self._operations = []

    def state(self, **budgets):
        raise ValueError('LargeCircuit requires an explicit stabilizer, clifford_t, clifford_frame or jya_frame observation engine')
