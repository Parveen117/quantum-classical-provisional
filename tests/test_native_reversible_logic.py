"""Independent integer, exact-amplitude and model-counterexample checks."""
from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc.calculator import calculate
from native_relational_qc.compact import CompactCircuit,CompactState,ResourceLimit
from native_relational_qc.entropy_logic import ThresholdModel,transport_split,expected_carry_activity
from native_relational_qc.exact import ONE,ZERO,INV_SQRT2,OMEGA,IMAG
from native_relational_qc.reversible_logic import BooleanMap,compile_oracle,gate_function,ripple_adder
from native_relational_qc.reversible_logic_demo import addition_search_circuit


def basis_action(operations,word):
    # Independent classical basis oracle. It never replaces coherent tests.
    for name,qubits in operations:
        if name not in ('x','cx','ccx'):
            raise ValueError('basis-only checker received a non-permutation gate')
        if all((word>>q)&1 for q in qubits[:-1]):
            word ^= 1<<qubits[-1]
    return word


class ReversibleLogicTests(unittest.TestCase):
    def test_all_256_three_input_boolean_functions_and_both_targets(self):
        for truth_word in range(256):
            function=BooleanMap(3,1,tuple((truth_word>>x)&1 for x in range(8)))
            program=compile_oracle(function)
            for x in range(8):
                for y in range(2):
                    before=x|(y<<3)
                    after=basis_action(program.circuit.operations,before)
                    self.assertEqual(after,x|((y^function.table[x])<<3))
                    self.assertEqual(basis_action(tuple(reversed(program.circuit.operations)),after),before)

    def test_named_gates_retain_inputs_and_do_not_merge_xor_preimages(self):
        for name in ('not','and','or','nand','nor','xor','xnor'):
            function=gate_function(name);program=compile_oracle(function)
            outputs=set()
            for word in range(1<<(function.input_bits+1)):
                x=word&((1<<function.input_bits)-1);y=word>>function.input_bits
                after=basis_action(program.circuit.operations,word)
                self.assertEqual(after,x|((y^function.table[x])<<function.input_bits))
                outputs.add(after)
            self.assertEqual(len(outputs),1<<(function.input_bits+1))
        self.assertEqual(gate_function('xor').table[0],gate_function('xor').table[3])
        self.assertNotEqual(basis_action(compile_oracle(gate_function('xor')).circuit.operations,0),
                            basis_action(compile_oracle(gate_function('xor')).circuit.operations,3))

    def test_multiple_outputs_and_higher_degree_scratch(self):
        rng=random.Random(20261023)
        for n,m in ((4,3),(6,2),(8,1)):
            table=tuple(rng.randrange(1<<m) for _ in range(1<<n))
            program=compile_oracle(BooleanMap(n,m,table))
            self.assertLessEqual(len(program.scratch),max(0,n-2))
            for x in range(1<<n):
                for y in range(1<<m):
                    self.assertEqual(basis_action(program.circuit.operations,x|(y<<n)),x|((y^table[x])<<n))

    def test_constant_function_and_explicit_gate_budget(self):
        program=compile_oracle(BooleanMap(0,2,(3,)))
        self.assertEqual(basis_action(program.circuit.operations,0),3)
        self.assertEqual(compile_oracle(BooleanMap(2,1,(0,0,0,0)),max_gates=0).circuit.operations,())
        with self.assertRaises(ResourceLimit):compile_oracle(gate_function('nand'),max_gates=1)

    def test_quantum_phase_kickback_and_interference(self):
        program=compile_oracle(gate_function('xor'))
        circuit=CompactCircuit(3).add('h',0).add('h',1).add('x',2).add('h',2)
        program.append_to(circuit)
        circuit.add('h',0).add('h',1)
        state=circuit.state()
        self.assertEqual(state.probability({0:1,1:1}),ONE)
        self.assertEqual(state.amplitude(3),INV_SQRT2)
        self.assertEqual(state.amplitude(7),-INV_SQRT2)

    def test_entangled_inputs_complex_phase_and_clean_oracle_workspace(self):
        # Cubic function needs one workspace qubit, and f(111)=1.
        program=compile_oracle(BooleanMap(3,1,(0,0,0,0,0,0,0,1)))
        state=CompactState(program.circuit.n_qubits).apply('h',0).apply('t',0)
        state.apply('cx',0,1).apply('cx',1,2).apply('x',3).apply('h',3)
        original=state.fingerprint()
        for name,qs in program.circuit.operations:state.apply(name,*qs)
        self.assertEqual(state.amplitude(0),INV_SQRT2**2)
        self.assertEqual(state.amplitude(7),-(INV_SQRT2**2)*OMEGA)
        self.assertEqual(state.amplitude(8),-(INV_SQRT2**2))
        self.assertEqual(state.amplitude(15),(INV_SQRT2**2)*OMEGA)
        self.assertEqual(state.probability({q:0 for q in program.scratch}),ONE)
        for name,qs in reversed(program.circuit.operations):state.apply(name,*qs)
        self.assertEqual(state.fingerprint(),original)

    def test_dirty_workspace_is_not_silently_reset(self):
        program=compile_oracle(BooleanMap(3,1,(0,0,0,0,0,0,0,1)))
        dirty=(1<<program.scratch[0])|4
        after=basis_action(program.circuit.operations,dirty)
        self.assertNotEqual(after,dirty)  # Clean-workspace function promise does not apply.
        self.assertEqual(basis_action(tuple(reversed(program.circuit.operations)),after),dirty)

    def test_mapped_composition_and_validation_is_transactional(self):
        program=compile_oracle(gate_function('and'))
        circuit=CompactCircuit(5).add('x',4).add('x',2)
        program.append_to(circuit,(4,2,0))
        self.assertEqual(circuit.state().amplitude(21),ONE)
        saved=circuit.operations
        for mapping in ((0,0,1),(0,1),(0,1,5),(0,True,2)):
            with self.assertRaises(ValueError):program.append_to(circuit,mapping)
            self.assertEqual(circuit.operations,saved)
        program.append_to(circuit,(4,2,0),inverse=True)
        self.assertEqual(circuit.state().amplitude(20),ONE)

    def test_invalid_tables_widths_types_and_names(self):
        for args in ((True,1,(0,1)),(9,1,(0,)),(1,0,(0,1)),(1,1,(0,)),(1,1,(0,2)),(1,1,(0,True))):
            with self.assertRaises(ValueError):BooleanMap(*args)
        with self.assertRaises(TypeError):compile_oracle([])
        for name in ('NAND','unknown',True,[]):
            with self.assertRaises(ValueError):gate_function(name)
        for width in (0,64,True,1.5):
            with self.assertRaises(ValueError):ripple_adder(width)


class ReversibleAdderTests(unittest.TestCase):
    def test_search_requires_output_uncomputation(self):
        good=addition_search_circuit().state()
        bad=addition_search_circuit(uncompute=False).state()
        self.assertEqual(good.probability({0:0,1:1}),ONE)
        self.assertEqual(bad.probability({0:0,1:1}).to_dict()['coefficients'],['1/4','0','0','0'])
        self.assertEqual(good.probability({q:0 for q in (5,6,7,8,10)}),ONE)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference not installed')
    def test_coherent_adder_against_independent_dense_statevector(self):
        import numpy as np
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
        program=ripple_adder(4);qc=QuantumCircuit(17)
        for q in program.inputs:qc.h(q)
        qc.t(0);qc.s(4)
        for name,qs in program.circuit.operations:getattr(qc,name)(*qs)
        reference=Statevector.from_instruction(qc).data
        expected=np.zeros(1<<17,dtype=complex)
        for word in range(512):
            total=(word&15)+((word>>4)&15)+(word>>8)
            expected[word|(total<<9)]=complex((INV_SQRT2**9)*(OMEGA if word&1 else ONE)*(IMAG if word&16 else ONE))
        np.testing.assert_allclose(reference,expected,atol=3e-14,rtol=0)

    def test_four_bit_full_truth_table_all_arbitrary_output_words(self):
        program=ripple_adder(4);operations=program.circuit.operations
        for inputs in range(512):
            a,b,cin=inputs&15,(inputs>>4)&15,inputs>>8
            for y in range(32):
                before=inputs|(y<<9)
                after=basis_action(operations,before)
                self.assertEqual(after,inputs|((y^(a+b+cin))<<9))

    def test_one_bit_adder_full_quantum_basis_and_inverse(self):
        program=ripple_adder(1)
        for word in range(32):
            state=CompactState(5)
            for q in range(5):
                if word&(1<<q):state.apply('x',q)
            original=state.fingerprint()
            for name,qs in program.circuit.operations:state.apply(name,*qs)
            inputs=word&7;y=word>>3;total=inputs.bit_count()
            self.assertEqual(state.amplitude(inputs|((y^total)<<3)),ONE)
            for name,qs in reversed(program.circuit.operations):state.apply(name,*qs)
            self.assertEqual(state.fingerprint(),original)

    def test_four_bit_superposition_all_512_complex_amplitudes_and_cleanup(self):
        program=ripple_adder(4);state=CompactState(17)
        for q in program.inputs:state.apply('h',q)
        state.apply('t',0).apply('s',4)
        original=state.fingerprint()
        for name,qs in program.circuit.operations:state.apply(name,*qs)
        normalization=INV_SQRT2**9
        for word in range(512):
            total=(word&15)+((word>>4)&15)+(word>>8)
            expected=normalization*(OMEGA if word&1 else ONE)*(IMAG if word&16 else ONE)
            self.assertEqual(state.amplitude(word|(total<<9)),expected)
        self.assertEqual(state.probability({q:0 for q in program.scratch}),ONE)
        self.assertEqual(state.probability(),ONE)
        for name,qs in reversed(program.circuit.operations):state.apply(name,*qs)
        self.assertEqual(state.fingerprint(),original)

    def test_linear_resources_and_wide_basis_arithmetic(self):
        rng=random.Random(117)
        for n in (1,4,8,32,63):
            program=ripple_adder(n);report=program.to_dict()
            self.assertEqual(report['n_qubits'],4*n+1)
            self.assertEqual(report['gates'],11*n-4)
            self.assertEqual(report['gate_counts'],{'ccx':4*n-2,'cx':7*n-2})
            for _ in range(20):
                a,b=rng.getrandbits(n),rng.getrandbits(n);cin=rng.randrange(2);y=rng.getrandbits(n+1)
                inputs=a|(b<<n)|(cin<<(2*n))
                self.assertEqual(basis_action(program.circuit.operations,inputs|(y<<(2*n+1))),
                                 inputs|((y^(a+b+cin))<<(2*n+1)))

    def test_existing_calculator_executes_four_bit_addition(self):
        program=ripple_adder(4);circuit=CompactCircuit(17)
        word=7|(9<<4)|(1<<8)
        for q in program.inputs:
            if word&(1<<q):circuit.add('x',q)
        program.append_to(circuit)
        doc=dict(schema='nrqc-calculator-v1',n_qubits=17,backend='observer',
                 operations=[[n,list(q)] for n,q in circuit.operations],queries=[
                     dict(id='sum17',kind='probability',outcomes={str(q):(17>>i)&1 for i,q in enumerate(program.outputs)}),
                     dict(id='clean',kind='probability',outcomes={str(q):0 for q in program.scratch})])
        report=calculate(doc)
        self.assertEqual(report['status'],'completed')
        self.assertTrue(all(row['value']['exact']==ONE.to_dict() for row in report['answers']))


class EntropyModelAuditTests(unittest.TestCase):
    def test_theta_squared_and_complement_decoder(self):
        model=ThresholdModel(k3=1,theta=2,threshold=2,margin=1)
        self.assertEqual(model.score(1,1),4)
        self.assertTrue(model.check(gate_function('and'))['passed'])
        nand=ThresholdModel(k3=1,theta=2,threshold=2,margin=1,high_is_one=False)
        program=compile_oracle(nand.certified_function(gate_function('nand')))
        for x in range(4):self.assertEqual(basis_action(program.circuit.operations,x),x|((1-int(x==3))<<2))

    def test_all_truth_rows_and_positive_margin_are_required(self):
        with self.assertRaises(ValueError):
            ThresholdModel(k1=1,k2=1,k3=-3).certified_function(gate_function('nand'))
        model=ThresholdModel(k1=1,k2=1,k3=-2)
        self.assertTrue(model.check(gate_function('xor'))['passed'])
        self.assertFalse(ThresholdModel(k3=1,threshold=1).check(gate_function('and'))['passed'])
        for options in ({'theta':0},{'margin':0},{'high_is_one':1}):
            with self.assertRaises(ValueError):ThresholdModel(**options)
        for value in (0.5,True,'1/2'):
            with self.assertRaises(TypeError):ThresholdModel(k1=value)

    def test_digital_compositions_reject_incorrect_single_input_demorgan(self):
        nand=lambda a,b:1-a*b
        nor=lambda a,b:(1-a)*(1-b)
        for a in range(2):
            for b in range(2):
                self.assertEqual(nand(1-a,1-b),a+b-a*b)
                self.assertEqual(nor(1-a,1-b),a*b)
                self.assertEqual(nor(a,nor(a,b)),(1-a)*b)
        self.assertNotEqual(nand(1-0,0),0)  # NOT on one input is not OR.
        self.assertNotEqual(nor(1-1,0),1*0)  # NOT on one input is not AND.

    def test_correlated_carry_overlap_is_zero_and_expectation_exact(self):
        for a in range(2):
            for b in range(2):
                for cin in range(2):
                    self.assertEqual(a*b*(a^b)*cin,0)
                    self.assertEqual(a*b+((a^b)*cin),(a+b+cin)//2)
        for p in (Fraction(0),Fraction(1,2),Fraction(1)):
            total=Fraction(0)
            for a in range(16):
                for b in range(16):
                    for cin in range(2):
                        carry=cin;activity=0
                        for i in range(4):
                            ai,bi=(a>>i)&1,(b>>i)&1
                            carry=ai*bi+(ai^bi)*carry;activity+=carry
                        total += Fraction(activity,256)*(p if cin else 1-p)
            self.assertEqual(total,expected_carry_activity(4,p))
        self.assertEqual(expected_carry_activity(4),2)
        self.assertEqual(expected_carry_activity(4,Fraction(0)),Fraction(49,32))
        for p in (Fraction(-1),Fraction(2)):
            with self.assertRaises(ValueError):expected_carry_activity(4,p)

    def test_antisymmetric_transport_has_no_scalar_entropy_contribution(self):
        result=transport_split(((2,3),(-1,4)),(1,2))
        self.assertEqual(result['total'],22)
        self.assertEqual(result['symmetric'],22)
        self.assertEqual(result['antisymmetric'],0)
        self.assertTrue(result['symmetric_psd'])
        for z in (-100,-3,0,7,100):
            changed=transport_split(((2,1+z),(1-z,4)),(1,2))
            self.assertEqual(changed['total'],22)
        self.assertFalse(transport_split(((-1,0),(0,-2)),(1,1))['symmetric_psd'])


if __name__=='__main__':unittest.main()
