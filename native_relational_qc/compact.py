"""Exact weighted decision diagrams for native relational circuit execution.

Share proportional conditional states, retaining their complete scalar ratios.
No dense amplitude array is allocated except by the explicit to_dense method.
This uses known weighted-DD ideas; it does not guarantee small graphs for all
circuits. Node, coefficient and work budgets fail closed with transactional gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import sys

from .exact import Exact, ZERO, ONE, exact_gate


class ResourceLimit(RuntimeError):
    pass


def _integer(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer in [{lower}, {upper}]")
    return value


@dataclass(frozen=True, slots=True)
class Edge:
    weight: Exact
    node: int


@dataclass(frozen=True, slots=True)
class Node:
    level: int
    low: Edge
    high: Edge


ZERO_EDGE = Edge(ZERO, 0)
ONE_EDGE = Edge(ONE, 0)


class CompactState:
    """Mutable exact pure state, initialized to |0...0>, q0 least significant.

    Each public gate commits only after exact norm verification. Resource-limit
    failure restores the prior state; no truncation or approximate node merging.
    """

    def __init__(self, n_qubits, *, max_nodes=100_000, max_coefficient_bits=4096, max_work=2_000_000):
        self.n_qubits = _integer(n_qubits, "qubits", 1, 256)
        self.max_nodes = _integer(max_nodes, "max_nodes", 1, 10_000_000)
        self.max_coefficient_bits = _integer(max_coefficient_bits, "coefficient bits", 2, 1_000_000)
        self.max_work = _integer(max_work, "max_work", 1, 1_000_000_000)
        self._nodes = {}
        self._unique = {}
        self._next = 1
        self._peak_nodes = 0
        self._peak_bits = 1
        self._work = 0
        self._total_work = 0
        self._adds = {}
        root = ONE_EDGE
        for level in range(n_qubits):
            root = self._make(level, root, ZERO_EDGE)
        self._root = root
        self._adds.clear()

    def _tick(self):
        self._work += 1
        self._total_work += 1
        if self._work > self.max_work:
            raise ResourceLimit("exact operation work budget exceeded; state was not approximated")

    def _edge(self, weight, node):
        if not weight:
            return ZERO_EDGE
        bits = weight.max_bits
        self._peak_bits = max(self._peak_bits, bits)
        if bits > self.max_coefficient_bits:
            raise ResourceLimit("exact coefficient bit budget exceeded")
        return Edge(weight, node)

    def _scale(self, scalar, edge):
        if scalar == ONE:
            return edge
        return self._edge(scalar * edge.weight, edge.node)

    def _make(self, level, low, high):
        self._tick()
        if not low.weight and not high.weight:
            return ZERO_EDGE
        for child in (low, high):
            if child.weight:
                actual_level = self._nodes[child.node].level if child.node else -1
                if actual_level != level - 1:
                    raise ArithmeticError("conditional-state level mismatch")
        factor = low.weight if low.weight else high.weight
        node = Node(level, self._edge(low.weight / factor, low.node),
                    self._edge(high.weight / factor, high.node))
        key = self._unique.get(node)
        if key is None:
            if len(self._nodes) >= self.max_nodes:
                raise ResourceLimit("exact node budget exceeded")
            key = self._next
            self._next += 1
            self._nodes[key] = node
            self._unique[node] = key
            self._peak_nodes = max(self._peak_nodes, len(self._nodes))
        return self._edge(factor, key)

    def _children(self, edge):
        node = self._nodes[edge.node]
        return self._scale(edge.weight, node.low), self._scale(edge.weight, node.high)

    def _add(self, left, right):
        self._tick()
        if not left.weight:
            return right
        if not right.weight:
            return left
        if left.node == right.node:
            return self._edge(left.weight + right.weight, left.node)
        key = (left, right)
        if key in self._adds:
            return self._adds[key]
        level = self._nodes[left.node].level
        if self._nodes[right.node].level != level:
            raise ArithmeticError("cannot add states at different levels")
        a, b = self._children(left)
        c, d = self._children(right)
        out = self._make(level, self._add(a, c), self._add(b, d))
        self._adds[key] = out
        return out

    def _single(self, root, target, matrix):
        @lru_cache(maxsize=None)
        def visit(node_id):
            self._tick()
            node = self._nodes[node_id]
            if node.level == target:
                a, b = node.low, node.high
                low = self._add(self._scale(matrix[0][0], a), self._scale(matrix[0][1], b))
                high = self._add(self._scale(matrix[1][0], a), self._scale(matrix[1][1], b))
                return self._make(node.level, low, high)
            if node.level < target:
                raise ArithmeticError("target missing from conditional-state chain")
            return self._make(node.level, descend(node.low), descend(node.high))

        def descend(edge):
            return self._scale(edge.weight, visit(edge.node)) if edge.weight else ZERO_EDGE
        try:
            return descend(root)
        finally:
            visit.cache_clear()

    def _restrict(self, root, assignments):
        @lru_cache(maxsize=None)
        def visit(node_id):
            self._tick()
            if node_id == 0:
                return ONE_EDGE
            node = self._nodes[node_id]
            value = assignments.get(node.level)
            low = ZERO_EDGE if value == 1 else descend(node.low)
            high = ZERO_EDGE if value == 0 else descend(node.high)
            return self._make(node.level, low, high)

        def descend(edge):
            return self._scale(edge.weight, visit(edge.node)) if edge.weight else ZERO_EDGE
        try:
            return descend(root)
        finally:
            visit.cache_clear()

    def _controlled(self, root, target, controls, matrix):
        if not controls:
            return self._single(root, target, matrix)
        selected = self._restrict(root, {q: 1 for q in controls})
        moved = self._single(selected, target, matrix)
        # (I-P)psi + U P psi retains all controlled-branch phase.
        return self._add(self._add(root, self._scale(-ONE, selected)), moved)

    def _collect(self):
        reachable = set()
        stack = [self._root.node] if self._root.weight else []
        while stack:
            key = stack.pop()
            if key == 0 or key in reachable:
                continue
            reachable.add(key)
            node = self._nodes[key]
            stack.extend(edge.node for edge in (node.low, node.high) if edge.weight)
        self._nodes = {key: self._nodes[key] for key in reachable}
        self._unique = {node: key for key, node in self._nodes.items()}
        self._adds.clear()

    def _q(self, q):
        return _integer(q, "qubit", 0, self.n_qubits - 1)

    def apply(self, name, *qargs):
        plan = operation_plan(self.n_qubits, name, qargs)
        old_root = self._root
        self._work = 0
        self._adds.clear()
        try:
            root = old_root
            for basic, target, controls in plan:
                root = self._controlled(root, target, controls, exact_gate(basic))
            if self._probability(root, {}) != ONE:
                raise ArithmeticError("exact norm was not preserved")
            self._root = root
        finally:
            self._collect()
        return self

    def _probability(self, root, assignments):
        @lru_cache(maxsize=None)
        def visit(node_id):
            self._tick()
            if node_id == 0:
                return ONE
            node = self._nodes[node_id]
            bit = assignments.get(node.level)
            return ((branch(node.low) if bit != 1 else ZERO)
                    + (branch(node.high) if bit != 0 else ZERO))

        def branch(edge):
            out = edge.weight.norm2() * visit(edge.node) if edge.weight else ZERO
            if out.max_bits > self.max_coefficient_bits:
                raise ResourceLimit("observation coefficient bit budget exceeded")
            return out
        try:
            return branch(root)
        finally:
            visit.cache_clear()

    def probability(self, assignments=None):
        """Exact marginal probability. An empty assignment checks the whole norm."""
        assignments = {} if assignments is None else dict(assignments)
        for q, bit in assignments.items():
            self._q(q)
            _integer(bit, "outcome", 0, 1)
        self._work = 0
        return self._probability(self._root, assignments)

    def amplitude(self, index):
        if isinstance(index, str):
            if len(index) != self.n_qubits or any(c not in "01" for c in index):
                raise ValueError("bitstring must match the register, high qubit first")
            index = int(index, 2)
        _integer(index, "basis index", 0, 2**self.n_qubits - 1)
        edge = self._root
        weight = ONE
        while edge.weight:
            weight = weight * edge.weight
            if weight.max_bits > self.max_coefficient_bits:
                raise ResourceLimit("amplitude coefficient bit budget exceeded")
            if edge.node == 0:
                return weight
            node = self._nodes[edge.node]
            edge = node.high if (index >> node.level) & 1 else node.low
        return ZERO

    def expectation_z(self, qubits):
        """Exact expectation of a Z-string, without enumerating outcomes."""
        qubits = tuple(self._q(q) for q in qubits)
        if len(set(qubits)) != len(qubits):
            raise ValueError("Z-string qubits must be unique")
        selected = set(qubits)
        self._work = 0

        @lru_cache(maxsize=None)
        def visit(node_id):
            self._tick()
            if node_id == 0:
                return ONE
            node = self._nodes[node_id]
            low = branch(node.low)
            high = branch(node.high)
            out = low - high if node.level in selected else low + high
            if out.max_bits > self.max_coefficient_bits:
                raise ResourceLimit("observable coefficient bit budget exceeded")
            return out

        def branch(edge):
            return edge.weight.norm2() * visit(edge.node) if edge.weight else ZERO
        try:
            return branch(self._root)
        finally:
            visit.cache_clear()

    def to_dense(self, *, max_qubits=16):
        """Explicit diagnostic expansion only; never used for compact execution."""
        _integer(max_qubits, "dense limit", 1, 20)
        if self.n_qubits > max_qubits:
            raise ResourceLimit("explicit dense expansion exceeds caller's limit")
        import numpy as np
        return np.array([complex(self.amplitude(i)) for i in range(2**self.n_qubits)])

    def fingerprint(self):
        @lru_cache(maxsize=None)
        def node_hash(key):
            if key == 0:
                return "terminal-one"
            node = self._nodes[key]
            return hashlib.sha256((str(node.level) + ":" + edge_hash(node.low)
                                   + ":" + edge_hash(node.high)).encode()).hexdigest()

        def edge_hash(edge):
            return str(edge.weight.coefficients) + ":" + node_hash(edge.node)
        return hashlib.sha256(edge_hash(self._root).encode()).hexdigest()

    def stats(self):
        weights = {self._root.weight}
        for node in self._nodes.values():
            weights.update((node.low.weight, node.high.weight))
        seen = set()

        def deep_size(obj):
            if id(obj) in seen:
                return 0
            seen.add(id(obj))
            total = sys.getsizeof(obj)
            if isinstance(obj, dict):
                total += sum(deep_size(k) + deep_size(v) for k, v in obj.items())
            elif isinstance(obj, (tuple, list)):
                total += sum(deep_size(v) for v in obj)
            elif isinstance(obj, (Node, Edge, Exact)):
                total += sum(deep_size(getattr(obj, name)) for name in obj.__slots__)
            elif hasattr(obj, "numerator") and hasattr(obj, "denominator") and not isinstance(obj, int):
                total += deep_size(obj.numerator) + deep_size(obj.denominator)
            return total

        return {
            "qubits": self.n_qubits, "live_nodes": len(self._nodes),
            "peak_allocated_nodes": self._peak_nodes, "distinct_retained_weights": len(weights),
            "max_retained_coefficient_bits": max(w.max_bits for w in weights),
            "peak_edge_coefficient_bits": self._peak_bits,
            "retained_python_graph_bytes": deep_size((self._nodes, self._unique, self._root)),
            "dense_complex128_amplitude_bytes": 16 * 2**self.n_qubits,
            "cumulative_recursive_work_units": self._total_work,
        }


def operation_plan(n_qubits, name, qargs):
    qargs = tuple(_integer(q, "qubit", 0, n_qubits - 1) for q in qargs)
    if len(set(qargs)) != len(qargs):
        raise ValueError("gate qubits must be distinct")
    if name in {"cx", "cz", "ch", "cs", "ct"}:
        if len(qargs) != 2:
            raise ValueError("controlled gate requires two qubits")
        return [(name[1:], qargs[1], (qargs[0],))]
    if name == "ccx":
        if len(qargs) != 3:
            raise ValueError("ccx requires three qubits")
        return [("x", qargs[2], qargs[:2])]
    if name == "swap":
        if len(qargs) != 2:
            raise ValueError("swap requires two qubits")
        a, b = qargs
        return [("x", b, (a,)), ("x", a, (b,)), ("x", b, (a,))]
    exact_gate(name)
    if len(qargs) != 1:
        raise ValueError("single-qubit gate requires one qubit")
    return [(name, qargs[0], ())]


class CompactCircuit:
    """Named exact circuit IR. Observation queries refer to qubit indices."""

    def __init__(self, n_qubits):
        self.n_qubits = _integer(n_qubits, "qubits", 1, 256)
        self._operations = []

    @property
    def operations(self):
        return tuple(self._operations)

    def add(self, name, *qargs):
        operation_plan(self.n_qubits, name, qargs)
        self._operations.append((name, tuple(qargs)))
        return self

    def state(self, **budgets):
        out = CompactState(self.n_qubits, **budgets)
        for name, qargs in self._operations:
            out.apply(name, *qargs)
        return out
