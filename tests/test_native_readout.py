from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.dynamic import DynamicCircuit
from native_relational_qc.exact import Exact, ONE, HALF
from native_relational_qc.readout import real_sign, classical_distribution


class ReadoutTests(unittest.TestCase):
    def test_exact_order_in_quadratic_field(self):
        for value, sign in [(Exact(),0),(Exact(2,-1),1),(Exact(-2,1),-1),
                            (Exact(1,-1),-1),(Exact(-1,1),1),(Exact(b=-1),-1)]:
            self.assertEqual(real_sign(value),sign)
        with self.assertRaises(ValueError): real_sign(Exact(c=1))

    def test_full_correlated_readout_and_bit_order(self):
        c=DynamicCircuit(3,3).add('h',0).add('cx',0,1).add('x',2)
        for q in range(3):c.measure(q,q)
        self.assertEqual(dict(classical_distribution(c).probabilities),{'100':HALF,'111':HALF})
        self.assertEqual(dict(classical_distribution(c,[2,0]).probabilities),{'01':HALF,'11':HALF})

    def test_nonclifford_output_and_empty_reading(self):
        c=DynamicCircuit(1,1).add('h',0).add('t',0).add('h',0).measure(0,0)
        result=dict(classical_distribution(c).probabilities)
        self.assertEqual(result['0'],Exact(Fraction(1,2),Fraction(1,4)))
        self.assertEqual(result['1'],ONE-result['0'])
        self.assertEqual(dict(classical_distribution(c,[]).probabilities),{'':ONE})

    def test_many_deterministic_bits_do_not_expand_joint_projector(self):
        c=DynamicCircuit(1,64)
        for bit in range(64):c.measure(0,bit)
        result=classical_distribution(c,max_terms=2)
        self.assertEqual(dict(result.probabilities),{'0'*64:ONE})
        self.assertEqual(result.peak_query_terms,2)

    def test_budgets_and_invalid_bit_selections(self):
        c=DynamicCircuit(2,2).add('h',0).add('h',1).measure(0,0).measure(1,1)
        with self.assertRaises(ResourceLimit): classical_distribution(c,max_outcomes=2)
        with self.assertRaises(ResourceLimit): classical_distribution(c,max_queries=1)
        with self.assertRaises(ValueError): classical_distribution(c,[0,0])
        with self.assertRaises(ValueError): classical_distribution(c,[2])

    def test_original_workload_runs_with_quantum_sdk_imports_blocked(self):
        script = '''
import importlib.abc, json, sys
class BlockSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('qiskit','qiskit_aer','qiskit_ibm_runtime'):
            raise ImportError('quantum SDK deliberately blocked')
sys.meta_path.insert(0, BlockSDK())
from native_relational_qc.ibm_workloads import INPUTS, restore
from native_relational_qc.readout import classical_distribution
from native_relational_qc.exact import Exact
from fractions import Fraction
program=json.loads(INPUTS.read_text())['programs'][0]
result=classical_distribution(restore(program))
assert len(result.probabilities)==8
assert all(value==Exact(Fraction(1,8)) for _,value in result.probabilities)
assert not any(k.split('.')[0] in ('qiskit','qiskit_aer','qiskit_ibm_runtime') for k in sys.modules)
'''
        result = subprocess.run([sys.executable, '-c', script],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__=='__main__':unittest.main()
