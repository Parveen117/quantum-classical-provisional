import copy
from fractions import Fraction
import json
import random
import subprocess
import sys
import unittest

from native_relational_qc.calculator import calculate, display, loads, real_sign, run_calculation, validate
from native_relational_qc.exact import Exact, ONE, HALF


def request(operations=None, queries=None, **options):
    return dict(schema='nrqc-calculator-v1',n_qubits=2,
                operations=operations if operations is not None else [['h',[0]],['cx',[0,1]]],
                queries=queries if queries is not None else [dict(id='p00',kind='probability',outcomes={'0':0,'1':0})],
                **options)


def exact(value):
    return Exact(*(Fraction(x) for x in value['exact']['coefficients']))


class CalculatorTests(unittest.TestCase):
    def test_bell_probability_complex_observers_and_distribution(self):
        doc=request(queries=[dict(id='p00',kind='probability',outcomes={'0':0,'1':0}),
                             dict(id='yy',kind='expectation',paulis={'0':'Y','1':'Y'}),
                             dict(id='xx',kind='expectation',paulis={'0':'X','1':'X'}),
                             dict(id='law',kind='distribution',qubits=[1,0])])
        report=calculate(doc)
        self.assertEqual(report['status'],'completed')
        self.assertEqual([exact(r['value']) for r in report['answers'][:3]],[HALF,-ONE,ONE])
        law=report['answers'][3]
        self.assertEqual({k:exact(v) for k,v in law['probabilities'].items()},
                         {'00':HALF,'01':Exact(),'10':Exact(),'11':HALF})
        self.assertEqual(law['normalization'],ONE.to_dict())

    def test_bitstrings_follow_explicit_site_order(self):
        report=calculate(request([['x',[0]]],[dict(id='a',kind='distribution',qubits=[1,0]),
                                           dict(id='b',kind='distribution',qubits=[0,1])]))
        self.assertEqual(exact(report['answers'][0]['probabilities']['01']),ONE)
        self.assertEqual(exact(report['answers'][1]['probabilities']['10']),ONE)

    def test_phase_is_retained(self):
        doc=request([['h',[0]],['t',[0]],['h',[0]]],[dict(id='p',kind='probability',outcomes={'0':0})])
        self.assertEqual(exact(calculate(doc)['answers'][0]['value']),Exact(Fraction(1,2),Fraction(1,4)))

    def test_nonadjacent_backend_choice_is_explicit(self):
        doc=request([['h',[0]],['cx',[0,2]]],[dict(id='zz',kind='expectation',paulis={'0':'Z','2':'Z'})])
        doc['n_qubits']=3
        with self.assertRaises(ValueError):validate(doc)
        doc['backend']='observer'
        self.assertEqual(exact(calculate(doc)['answers'][0]['value']),ONE)

    def test_resource_failure_does_not_fabricate_answer(self):
        doc=request([['h',[0]],['t',[0]],['h',[0]]],
                    [dict(id='limited',kind='probability',outcomes={'0':0}),
                     dict(id='identity',kind='expectation',paulis={})],limits={'max_work':1})
        report=calculate(doc)
        self.assertEqual(report['status'],'incomplete')
        self.assertEqual(report['answers'][0]['status'],'resource_limit')
        self.assertNotIn('value',report['answers'][0])
        self.assertEqual(exact(report['answers'][1]['value']),ONE)
        doc['queries']=[dict(id='law',kind='distribution',qubits=[0])]
        failed=calculate(doc)['answers'][0]
        self.assertNotIn('probabilities',failed)
        self.assertNotIn('normalization',failed)

    def test_rejects_ambiguous_or_unsupported_input(self):
        with self.assertRaises(ValueError):loads('{"n_qubits":2,"n_qubits":3}')
        with self.assertRaises(ValueError):loads('{"x":NaN}')
        bad=[]
        for field,value in [('n_qubits',True),('schema','unknown'),('backend','auto'),
                            ('decimal_places',True),('operations',[['rz',[0]]]),
                            ('operations',[['cx',[0,0]]]),('limits',{'max_terms':1}),
                            ('limits',{'max_work':True}),('unexpected',1)]:
            doc=request();doc[field]=value;bad.append(doc)
        for outcomes in ({'01':0},{'-1':0},{'2':0},{'0':True},{'0':2}):
            bad.append(request(queries=[dict(id='bad',kind='probability',outcomes=outcomes)]))
        for doc in bad:
            with self.subTest(doc=doc),self.assertRaises((ValueError,TypeError)):validate(doc)

    def test_query_and_output_caps(self):
        doc=request();doc['queries']*=2
        with self.assertRaises(ValueError):validate(doc)
        doc=request(queries=[dict(id='a',kind='distribution',qubits=[0,0])])
        with self.assertRaises(ValueError):validate(doc)
        doc=request(queries=[dict(id='a',kind='distribution',qubits=list(range(8))),
                             dict(id='b',kind='probability',outcomes={})]);doc['n_qubits']=8
        with self.assertRaises(ValueError):validate(doc)

    def test_hashes_separate_circuit_from_query(self):
        doc=request(); changed=copy.deepcopy(doc);changed['queries'][0]['outcomes']['1']=1
        a,b=calculate(doc),calculate(changed)
        self.assertEqual(a['circuit_sha256'],b['circuit_sha256'])
        self.assertNotEqual(a['request_sha256'],b['request_sha256'])
        self.assertEqual(a['request_sha256'],calculate(dict(reversed(list(doc.items()))))['request_sha256'])

    def test_cli_stdin_and_legacy_commands(self):
        p=subprocess.run([sys.executable,'-m','native_relational_qc','calculate','-'],
                         input=json.dumps(request()),text=True,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        self.assertEqual(exact(result['answers'][0]['value']),HALF)
        self.assertIn('wall_seconds',result)
        p=subprocess.run([sys.executable,'-m','native_relational_qc','calculate','-'],
                         input='{"schema":"bad"}',text=True,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(p.stdout)['status'],'invalid_request')
        p=subprocess.run([sys.executable,'-m','native_relational_qc','bell'],
                         text=True,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['program'],'bell')

    def test_wall_timeout_returns_no_answer_and_rejects_bad_limits(self):
        result=run_calculation(request(),timeout_seconds=1e-9)
        self.assertEqual(result['status'],'time_limit')
        self.assertEqual(result['answers'],[])
        for cap in (0,-1,True,float('inf'),float('nan'),301):
            with self.assertRaises(ValueError):run_calculation(request(),timeout_seconds=cap)


class DecimalEnclosureTests(unittest.TestCase):
    def check_enclosure(self,value,places):
        result=display(value,places)
        lo=Fraction(result['decimal_enclosure']['lower'])
        hi=Fraction(result['decimal_enclosure']['upper'])
        middle=Fraction(result['decimal'])
        error=Fraction(result['decimal_enclosure']['maximum_absolute_display_error'])
        self.assertGreaterEqual(real_sign(value-Exact(lo)),0)
        self.assertGreaterEqual(real_sign(Exact(hi)-value),0)
        self.assertEqual(middle,(lo+hi)/2)
        self.assertEqual(error,(hi-lo)/2)
        self.assertLessEqual(error,Fraction(1,10**places))
        self.assertEqual(exact(result),value)

    def test_signed_rational_and_irrational_enclosures(self):
        rng=random.Random(117)
        for _ in range(100):
            value=Exact(Fraction(rng.randint(-100,100),rng.randint(1,100)),
                        Fraction(rng.randint(-100,100),rng.randint(1,100)))
            self.check_enclosure(value,rng.choice((0,6,12,30,60)))
        for v in (Exact(),HALF,-ONE,Exact(Fraction(1,3))):self.check_enclosure(v,12)
        self.assertEqual(display(HALF)['decimal_enclosure']['maximum_absolute_display_error'],'0')

    def test_large_cancellation_keeps_certified_interval(self):
        p,q=1,1
        for _ in range(90):p,q=p+2*q,p+q
        value=Exact(-p,q)
        self.assertNotEqual(real_sign(value),0)
        self.check_enclosure(value,60)
        self.check_enclosure(-value,60)


if __name__=='__main__':unittest.main()
