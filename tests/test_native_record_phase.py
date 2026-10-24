import random
import unittest

from native_relational_qc.calculator import calculate
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.phase_backend import PERMUTATIONS
from native_relational_qc.record_phase import SCHEMA,build_record,run_record,assess_record,calculate_record
from native_relational_qc.shor import build,exact_phase_law


def full_register(modulus,base,precision):
    program=build(modulus,base,precision=precision,oracle='arithmetic',rewrite='panini',field='flat')
    report=calculate(dict(program.request('cyclotomic_pow2'),limits={'max_branches':65_536,'max_work':1_000_000_000}))
    Z=field_of_order(max(8,1<<precision))
    return program,{int(k,2):Z.from_dict(v['exact']) for k,v in report['answers'][0]['probabilities'].items()}


class RecordPhaseTests(unittest.TestCase):
    def test_record_law_equals_full_register_and_fourier_law(self):
        for N,a,m in ((15,2,3),(15,7,4),(21,2,5),(33,5,6)):
            program=build_record(N,a,precision=m)
            distribution,budget=run_record(program)
            law=exact_phase_law(N,a,m,field='flat')
            self.assertEqual(distribution,law,(N,a,m))
            full,readout=full_register(N,a,m)
            self.assertEqual(distribution,readout,(N,a,m))
            self.assertEqual(program.n_qubits,1+len(full.work)+len(full.scratch))   # one control wire for every m
            self.assertLess(program.n_qubits,full.circuit.n_qubits)
            self.assertEqual(budget.stats['leaves']+budget.stats['pruned_records'],1<<m)
            self.assertEqual(assess_record(program,distribution)['status'],'verified')

    def test_period_dividing_the_record_length_gives_a_four_point_law(self):
        # a=2 mod 15 has order 4, so every record is an exact multiple of 2**(m-2).
        for m in (3,4,6):
            program=build_record(15,2,precision=m);distribution,budget=run_record(program);Z=program.field
            quarter=Z(1)/4
            for y,value in distribution.items():
                self.assertEqual(value,quarter if y%(1<<(m-2))==0 else Z(),(m,y))
            self.assertEqual(budget.stats['pruned_records'],(1<<m)-4)

    def test_correction_uses_only_retained_readings(self):
        rng=random.Random(5)
        for m in (3,7,12):
            program=build_record(21,2,precision=m);M=program.order
            for _ in range(20):
                readings=[rng.randrange(2) for _ in range(m)]
                for level in range(m):
                    # -M * sum_{s<t} y_s 2**(s-t-1), as an integer exponent of zeta_M.
                    expected=-sum(readings[s]*(M>>(level+1-s)) for s in range(level))
                    self.assertEqual(program.correction_exponent(level,readings),expected)
                    # Later readings never change the correction.
                    changed=readings[:level]+[1-y for y in readings[level:]]
                    self.assertEqual(program.correction_exponent(level,changed),expected)

    def test_build_validation_and_permutation_only_rounds(self):
        for bad in (dict(modulus=16),dict(modulus=15,base=3),dict(precision=13),dict(precision=0)):
            with self.assertRaises(ValueError):build_record(**{**dict(modulus=15,base=2,precision=3),**bad})
        program=build_record(21,2,precision=4)
        self.assertEqual([j for j,_,_ in program.rounds],[3,2,1,0])
        self.assertEqual([b for _,b,_ in program.rounds],[pow(2,8,21),pow(2,4,21),pow(2,2,21),2])
        for _,_,circuit in program.rounds:
            self.assertTrue(all(name in PERMUTATIONS for name,_ in circuit.operations))

    def test_report_shape_and_budget_failure(self):
        program=build_record(15,7,precision=3)
        report=calculate_record(program)
        self.assertEqual(report['schema'],SCHEMA);self.assertEqual(report['status'],'completed')
        self.assertEqual(set(report['record']['probabilities']),{format(y,'03b') for y in range(8)})
        self.assertEqual(report['assessment']['status'],'verified')
        self.assertTrue(report['assessment']['exact_fourier_law_agrees'])
        self.assertEqual(report['statistics']['peak_support'],4)
        failed=calculate_record(program,max_work=50)
        self.assertEqual(failed['status'],'incomplete');self.assertNotIn('record',failed)
        self.assertEqual(failed['statistics']['work_used'],51)
        with self.assertRaises(ResourceLimit):run_record(program,max_branches=2)


if __name__=='__main__':unittest.main()
