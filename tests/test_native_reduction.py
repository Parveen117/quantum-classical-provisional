"""Exact full-operator checks, including every input basis and global phase."""
import copy
import random
import unittest

from native_relational_qc.calculator import calculate, validate
from native_relational_qc.compact import CompactCircuit
from native_relational_qc.exact import ONE, ZERO, IMAG, exact_gate
from native_relational_qc.reduction import reduce_circuit


SINGLES = ('id','x','y','z','r','k','rk','h','s','sdg','t','tdg','sx','sxdg')


def evolve(n, operations, basis):
    # Small independent dense oracle. The production reducer does not execute
    # a state, and this oracle does not use its pair table or stack algorithm.
    values = [ONE if i == basis else ZERO for i in range(1 << n)]
    for name, qubits in operations:
        if name == 'swap':
            a,b = qubits
            mask = (1 << a) | (1 << b)
            values = [values[i ^ mask] if ((i >> a) ^ (i >> b)) & 1 else values[i]
                      for i in range(1 << n)]
            continue
        controls = qubits[:-1] if name.startswith('c') else ()
        target = qubits[-1]
        matrix = exact_gate('x' if name == 'ccx' else name[1:] if controls else name)
        for low in range(1 << n):
            if (low >> target) & 1 or any(not (low >> q) & 1 for q in controls):
                continue
            high = low | (1 << target)
            a,b = values[low],values[high]
            values[low] = matrix[0][0]*a + matrix[0][1]*b
            values[high] = matrix[1][0]*a + matrix[1][1]*b
    return values


def circuit(n, operations):
    out = CompactCircuit(n)
    for name, qubits in operations:
        out.add(name, *qubits)
    return out


class ExactReductionTests(unittest.TestCase):
    def assert_operator(self, original):
        saved = original.operations
        reduced = reduce_circuit(original)
        for basis in range(1 << original.n_qubits):
            a = evolve(original.n_qubits, saved, basis)
            b = evolve(original.n_qubits, reduced.circuit.operations, basis)
            self.assertEqual(a, [reduced.phase*v for v in b])
        self.assertEqual(original.operations, saved)
        again = reduce_circuit(reduced.circuit)
        self.assertEqual(again.circuit.operations, reduced.circuit.operations)
        self.assertEqual(again.phase, ONE)
        return reduced

    def test_every_named_single_pair_as_full_operator(self):
        for earlier in SINGLES:
            for later in SINGLES:
                with self.subTest(earlier=earlier,later=later):
                    self.assert_operator(circuit(1,[(earlier,(0,)),(later,(0,))]))

    def test_phase_ledger_cannot_be_erased_for_amplitudes(self):
        result = self.assert_operator(circuit(1,[('x',(0,)),('y',(0,))]))
        self.assertEqual(result.circuit.operations,(('z',(0,)),))
        self.assertEqual(result.phase,-IMAG)
        result = self.assert_operator(circuit(1,[('r',(0,)),('r',(0,))]))
        self.assertEqual(result.circuit.operations,())
        self.assertEqual(result.phase,-ONE)

    def test_controlled_rules_on_every_input_basis(self):
        for name in ('cx','cz','ch','cs','ct','swap','ccx'):
            operands = (0,1,2) if name == 'ccx' else (1,0)
            with self.subTest(name=name):
                result = self.assert_operator(circuit(3,[(name,operands),(name,operands)]))
                self.assertEqual(result.phase,ONE)
                self.assertEqual(len(result.circuit.operations),int(name in ('cs','ct')))

    def test_conditional_phase_is_retained(self):
        result = self.assert_operator(circuit(2,[('cs',(1,0)),('cs',(1,0))]))
        self.assertEqual(result.circuit.operations,(('cz',(0,1)),))
        self.assertEqual(evolve(2,result.circuit.operations,3)[3],-ONE)
        result = self.assert_operator(circuit(2,[('ct',(0,1))]*4))
        self.assertEqual(result.circuit.operations,(('cz',(0,1)),))

    def test_disjoint_crossings_and_cascading_cancellation(self):
        original = circuit(3,[('h',(0,)),('t',(1,)),('h',(0,)),('tdg',(1,)),
                              ('cx',(0,1)),('x',(2,)),('cx',(0,1)),('x',(2,))])
        self.assertEqual(self.assert_operator(original).circuit.operations,())

    def test_overlapping_support_and_control_direction_block_cancellation(self):
        for operations in ([('h',(0,)),('cx',(0,1)),('h',(0,))],
                           [('cx',(0,1)),('cx',(1,0))],
                           [('h',(0,)),('t',(0,)),('h',(0,))]):
            with self.subTest(operations=operations):
                result = self.assert_operator(circuit(2,operations))
                self.assertEqual(result.circuit.operations,tuple(operations))

    def test_symmetric_operands_and_aliases(self):
        original = circuit(3,[('cz',(1,0)),('cz',(0,1)),('swap',(2,0)),('swap',(0,2)),
                              ('ccx',(1,0,2)),('ccx',(0,1,2)),('k',(0,)),('z',(0,)),
                              ('rk',(1,)),('x',(1,)),('r',(2,)),('y',(2,)),('id',(0,))])
        result = self.assert_operator(original)
        self.assertEqual(result.circuit.operations,())
        self.assertEqual(result.phase,-IMAG)

    def test_random_mixed_circuits_full_operator(self):
        rng = random.Random(20261023)
        for case in range(24):
            original = CompactCircuit(3)
            for _ in range(24):
                name = rng.choice(SINGLES+('cx','cz','ch','cs','ct','swap','ccx'))
                arity = 3 if name == 'ccx' else 2 if name in ('cx','cz','ch','cs','ct','swap') else 1
                original.add(name,*rng.sample(range(3),arity))
            with self.subTest(case=case):
                self.assert_operator(original)

    def test_input_cap_and_type(self):
        with self.assertRaises(TypeError):reduce_circuit([])
        for cap in (-1,True,1_000_001):
            with self.assertRaises(ValueError):reduce_circuit(CompactCircuit(1),max_input_gates=cap)
        with self.assertRaises(ValueError):
            reduce_circuit(CompactCircuit(1).add('h',0),max_input_gates=0)


class CalculatorReductionTests(unittest.TestCase):
    def test_opt_in_preserves_values_phase_and_original_hash(self):
        doc = dict(schema='nrqc-calculator-v1',n_qubits=2,
                   operations=[['h',[0]],['cx',[0,1]],['x',[1]],['y',[1]]],
                   queries=[dict(id='yy',kind='expectation',paulis={'0':'Y','1':'Y'}),
                            dict(id='law',kind='distribution',qubits=[0,1])])
        plain = calculate(doc)
        selected = copy.deepcopy(doc);selected['simplify']='exact'
        reduced = calculate(selected)
        self.assertEqual(plain['circuit_sha256'],reduced['circuit_sha256'])
        self.assertNotEqual(plain['request_sha256'],reduced['request_sha256'])
        self.assertEqual(plain['answers'][0]['value'],reduced['answers'][0]['value'])
        self.assertEqual(plain['answers'][1]['probabilities'],reduced['answers'][1]['probabilities'])
        self.assertEqual(reduced['gates'],4)
        self.assertEqual(reduced['simplification']['output_gates'],3)
        self.assertEqual(reduced['simplification']['global_phase'],(-IMAG).to_dict())
        self.assertNotIn('simplification',plain)
        doc['simplify']='none'
        self.assertEqual(calculate(doc)['request_sha256'],plain['request_sha256'])

    def test_validation_and_observer_backend(self):
        doc = dict(schema='nrqc-calculator-v1',n_qubits=3,
                   operations=[['ccx',[0,1,2]],['ccx',[1,0,2]]],simplify='exact',
                   queries=[dict(id='p',kind='probability',outcomes={'0':0})])
        with self.assertRaises(ValueError):validate(doc)  # Validate original backend scope first.
        doc['backend']='observer'
        self.assertEqual(calculate(doc)['simplification']['output_gates'],0)
        for invalid in (True,'auto',[],{},None):
            doc['simplify']=invalid
            with self.assertRaises(ValueError):validate(doc)


if __name__ == '__main__':
    unittest.main()
