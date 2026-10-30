"""Independent circuits, native labels, data separation and fail-closed training."""
import copy
from fractions import Fraction as Q
import math
import random
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.exact import Exact
from native_relational_qc.cyclotomic import Cyclotomic
from native_relational_qc.cyclotomic32 import Cyclotomic32
from native_relational_qc.cyclotomic64 import Cyclotomic64
from native_relational_qc.phase_backend import PhaseCircuit,Phase32Circuit,Phase64Circuit,PowerPhaseCircuit,prepare
from native_relational_qc.self_learning import (
    FIELD,Example,Evaluator,circuit,fit,assess,packet,load_packet,digest,information_ceiling,
)
from native_relational_qc.learning_tasks import xor_examples,curvature_case,curvature_splits,classical_baselines
from native_relational_qc.compact import ResourceLimit


def embed(value):
    if type(value) is Exact:return FIELD(value)
    for cls,order in ((Cyclotomic,16),(Cyclotomic32,32),(Cyclotomic64,64)):
        if type(value) is cls:return embed(value.lo)+embed(value.hi)*FIELD.root(64//order)
    raise TypeError(type(value))


def dense_probability(features,params):
    state=np.zeros(16,dtype=complex);state[0]=1
    def ry(q,steps):
        theta=steps*math.pi/32; a,b=math.cos(theta/2),math.sin(theta/2)
        for label in range(16):
            if not label&(1<<q):
                other=label|(1<<q);x,y=state[label],state[other]
                state[label]=a*x-b*y;state[other]=b*x+a*y
    for q,s in enumerate(features):ry(q,s)
    for q,s in enumerate(params[:4]):ry(q,s)
    for control,target in ((0,2),(1,2),(2,3)):
        out=np.zeros(16,dtype=complex)
        for label,v in enumerate(state):out[label^(1<<target) if label&(1<<control) else label]=v
        state=out
    ry(3,params[4])
    return sum(abs(v)**2 for k,v in enumerate(state) if k&8)


class SelfLearningTests(unittest.TestCase):
    def test_all_three_legacy_phase_executors_keep_exact_actions(self):
        for cls,order in ((PhaseCircuit,16),(Phase32Circuit,32),(Phase64Circuit,64)):
            old=cls(3);flat=PowerPhaseCircuit(3,64)
            operations=(("h",(0,)),(f"p{order}",(0,)),("h",(1,)),
                        (f"cp{order}",(0,1)),("cx",(1,2)),("h",(0,)),("sdg",(2,)))
            for name,qs in operations:old.add(name,*qs);flat.add(name,*qs)
            self.assertEqual(prepare(flat).amplitudes,{k:embed(v) for k,v in prepare(old).amplitudes.items()})

    def test_flat_execution_matches_unchanged_nested_fields_without_phase_alignment(self):
        rng=random.Random(1031)
        for _ in range(12):
            features=tuple(rng.randrange(64) for _ in range(2));params=tuple(rng.randrange(64) for _ in range(5))
            flat=circuit(features,params);old=Phase64Circuit(4)
            for name,qs in flat.operations:old.add({"p2":"z","p4":"s","p8":"t"}.get(name,name),*qs)
            actual=prepare(flat).amplitudes;expected={k:embed(v) for k,v in prepare(old).amplitudes.items()}
            self.assertEqual(actual,expected)

    def test_probabilities_match_independent_real_rotation_circuit(self):
        rng=random.Random(1603);evaluator=Evaluator()
        for _ in range(24):
            f=tuple(rng.randrange(64) for _ in range(2));p=tuple(rng.randrange(64) for _ in range(5))
            self.assertAlmostEqual(complex(evaluator.probability(f,p)).real,dense_probability(f,p),places=12)

    def test_xor_is_a_four_case_sanity_task(self):
        evaluator=Evaluator()
        for row in xor_examples():self.assertEqual(evaluator.probability(row.features,(0,0,0,0,0)),FIELD(row.target))

    def test_native_curvature_labels_and_positive_patch(self):
        point_values=set()
        for u in (-7,-2,1,6):
            for v in (-6,-1,2,7):
                example,source=curvature_case(u,v)
                self.assertEqual(Q(source["curvature"]),Q(u*v,324))
                self.assertEqual(example.target,int(u*v<0))
                self.assertGreater(Q(source["patch_lower_eigenvalue"]),0)
                point_values.add(tuple(source["six_point_responses"].values()))
        self.assertEqual(len(point_values),1)

    def test_split_has_no_shared_magnitudes_or_examples(self):
        splits,source=curvature_splits()
        self.assertEqual({k:len(v) for k,v in splits.items()},{"train":16,"validation":4,"test":64})
        ids=[{x.name for x in splits[k]} for k in ("train","validation","test")]
        self.assertFalse(ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2])
        mags=[{abs(int(source["source_records"][e.name]["u"])) for e in splits[k]} for k in splits]
        self.assertFalse(mags[0]&mags[1] or mags[0]&mags[2] or mags[1]&mags[2])

    def test_point_only_information_ceiling_is_half(self):
        rows,_=curvature_splits(view="point_only")
        for split in rows.values():
            ceiling=information_ceiling(split)
            self.assertEqual(ceiling["distinct_inputs"],1)
            self.assertEqual(ceiling["accuracy_ceiling"],"1/2")
        # Identical records cannot receive different predictions even with
        # arbitrary circuit parameters; balanced labels give loss >= 1/4.
        ev=Evaluator();p=ev.probability(rows["test"][0].features,(8,16,24,32,40))
        loss=(p*p+(1-p)*(1-p))/2
        self.assertGreaterEqual((loss-Q(1,4)).real_sign(),0)

    def test_classical_product_baseline_and_linear_control(self):
        rows,_=curvature_splits();baseline=classical_baselines(rows["train"],rows["test"])
        self.assertEqual(baseline["linear_ols"]["accuracy"],"1/2")
        self.assertEqual(baseline["product_regression"]["coefficient"],"1/25")
        self.assertEqual(baseline["product_regression"]["accuracy"],"1")

    def test_optimizer_only_sees_supplied_training_features_and_accepts_decreases(self):
        train=(Example("t0",(0,0),0),Example("t1",(32,0),1));seen=[]
        def objective_probability(self,features,params):
            seen.append(features);p=FIELD(Q(abs(32-params[0]),32))
            return p if features[0]==32 else 1-p
        with patch.object(Evaluator,"probability",objective_probability):
            result=fit(train,view="first_layer",seeds=(17,),sweeps=2)
        self.assertEqual(set(seen),{e.features for e in train})
        self.assertEqual(result["training_ids"],["t0","t1"])
        self.assertEqual(result["model"]["phase_steps"][0],0)
        events=result["trace"][0]["events"]
        for before,after in zip(events,events[1:]):
            self.assertLess((FIELD.from_dict(after["loss"])-FIELD.from_dict(before["loss"])).real_sign(),0)

    def test_model_roundtrip_tampering_and_feature_contract(self):
        model=packet((0,0,0,0,0),training_digest="a"*64,view="xor_bits")
        self.assertEqual(load_packet(model),(0,)*5)
        self.assertEqual(assess(model,xor_examples())["accuracy"],"1")
        altered=copy.deepcopy(model);altered["phase_steps"][0]=8
        with self.assertRaises(ValueError):load_packet(altered)
        altered=copy.deepcopy(model);altered["hardware_authorized"]=True
        with self.assertRaises(ValueError):load_packet(altered)
        with self.assertRaises(ValueError):assess(model,(curvature_case(1,1)[0],))

    def test_whole_run_budgets_and_cache_are_explicit(self):
        ev=Evaluator(max_circuits=1)
        p=ev.probability((0,0),(0,)*5)
        self.assertEqual(ev.probability((0,0),(0,)*5),p)
        self.assertEqual((ev.stats["circuit_executions"],ev.stats["cache_hits"]),(1,1))
        with self.assertRaises(ResourceLimit):ev.probability((0,32),(0,)*5)
        with self.assertRaises(ResourceLimit):fit(xor_examples(),view="xor_bits",evaluator=Evaluator(max_circuits=1),seeds=(17,))
        with self.assertRaises(ResourceLimit):Evaluator(max_work=1).probability((16,16),(8,)*5)

    def test_training_view_and_input_limits_fail_closed(self):
        for value in (True,1.5,-1,64):
            with self.assertRaises(ValueError):circuit((value,0),(0,)*5)
        with self.assertRaises(ValueError):Example("bad",(0,0),True)
        with self.assertRaises(ValueError):Example("bad",(0,0),0,"unknown")
        with self.assertRaises(ValueError):fit(xor_examples(),view="first_layer")
        with self.assertRaises(ValueError):fit((xor_examples()[0],)*2,view="xor_bits")
        with self.assertRaises(ValueError):fit(xor_examples(),view="xor_bits",seeds=())
        with self.assertRaises(ValueError):curvature_case(0,1)
        with self.assertRaises(ValueError):curvature_case(8,1)


if __name__=="__main__":unittest.main()
