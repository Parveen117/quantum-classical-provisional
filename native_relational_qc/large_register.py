"""Iterative circuit description for explicitly selected large-register engines."""
from .compact import CompactCircuit, _integer

MAX_LARGE_QUBITS = 2056


class LargeCircuit(CompactCircuit):
    """Named circuit IR only; it does not allocate a recursive state graph."""
    def __init__(self, n_qubits):
        self.n_qubits = _integer(n_qubits, 'qubits', 1, MAX_LARGE_QUBITS)
        self._operations = []

    def state(self, **budgets):
        raise ValueError('LargeCircuit requires an explicit stabilizer, clifford_t, clifford_frame or jya_frame observation engine')
