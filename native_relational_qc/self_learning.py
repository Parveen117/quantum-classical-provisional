"""Bounded classical training of a four-qubit variational circuit.

Uses the existing exact phase executor. No hardware feedback, proof oracle,
neural speedup or universal optimization claim. See SELF_LEARNING.md.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
import random

from .compact import ResourceLimit
from .cyclotomic_pow2 import field_of_order
from .phase_backend import PowerPhaseCircuit, prepare

FIELD=field_of_order(64)
ARCHITECTURE="four-qubit-parity-five-ry-v1"
VIEWS=("xor_bits","first_layer","point_only")


def _int(value, name, low, high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f"{name} must be an integer in [{low},{high}]")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _steps(values,n):
    if not isinstance(values,(tuple,list)) or len(values)!=n:
        raise ValueError(f"exactly {n} phase-step integers required")
    return tuple(_int(v,"phase step",0,63) for v in values)


@dataclass(frozen=True)
class Example:
    name: str
    features: tuple
    target: int
    view: str = "first_layer"

    def __post_init__(self):
        if type(self.name) is not str or not 1<=len(self.name)<=80:
            raise ValueError("example needs a short stable ID")
        object.__setattr__(self,"features",_steps(self.features,2))
        _int(self.target,"binary target",0,1)
        if self.view not in VIEWS:raise ValueError("unknown example feature view")

    def record(self):return dict(id=self.name,features=list(self.features),target=self.target,view=self.view)


def _examples(examples):
    if not isinstance(examples,(tuple,list)) or not 1<=len(examples)<=256:
        raise ValueError("require 1..256 explicitly labelled examples")
    if any(type(e) is not Example for e in examples):raise ValueError("validated examples required")
    if len({e.name for e in examples})!=len(examples):raise ValueError("duplicate example IDs")
    return tuple(examples)


def _ry(circuit,q,steps):
    """RY(theta) up to a retained global phase; theta=steps*pi/32."""
    if not steps:return
    circuit.add("sdg",q).add("h",q)
    for bit in range(6):
        if steps&(1<<bit):circuit.add(f"p{64//(1<<bit)}",q)
    circuit.add("h",q).add("s",q)


def circuit(features,parameters):
    features=_steps(features,2);parameters=_steps(parameters,5)
    c=PowerPhaseCircuit(4,64)
    for q,step in enumerate(features):_ry(c,q,step)
    for q,step in enumerate(parameters[:4]):_ry(c,q,step)
    for a,b in ((0,2),(1,2),(2,3)):c.add("cx",a,b)
    _ry(c,3,parameters[4])
    return c


class Evaluator:
    """One budget across optimization and evaluation, with an explicit cache.

    engine_work counts executor work, not all Python/optimizer overhead;
    wall time is separately measured by the audit. No label enters execution.
    """
    def __init__(self,*,max_circuits=16000,max_work=100_000_000):
        self.max_circuits=_int(max_circuits,"circuit budget",1,100000)
        self.max_work=_int(max_work,"executor work budget",1,1_000_000_000)
        self.cache={}
        self.stats=dict(circuit_executions=0,cache_hits=0,engine_work=0,objective_evaluations=0,
                        peak_support=0,total_executed_gates=0,hardware_jobs=0)

    def probability(self,features,parameters):
        features=_steps(features,2);parameters=_steps(parameters,5);key=(features,parameters)
        if key in self.cache:
            self.stats["cache_hits"]+=1;return self.cache[key]
        if self.stats["circuit_executions"]>=self.max_circuits or self.stats["engine_work"]>=self.max_work:
            raise ResourceLimit("whole learning-run execution budget exhausted; no completed model returned")
        c=circuit(features,parameters)
        self.stats["circuit_executions"]+=1
        self.stats["total_executed_gates"]+=len(c.operations)
        remaining=min(100000,self.max_work-self.stats["engine_work"])
        state=None
        try:
            state=prepare(c,max_work=remaining,max_branches=16,max_coefficient_bits=4096)
            value=state.probability({3:1})
        except ResourceLimit as error:
            used=state.budget.stats if state is not None else getattr(error,"statistics",{})
            self.stats["engine_work"]+=used.get("work_used",0)
            raise
        self.stats["engine_work"]+=state.budget.stats["work_used"]
        self.stats["peak_support"]=max(self.stats["peak_support"],state.budget.stats["peak_branches"])
        if value.real_sign()<0 or (FIELD(1)-value).real_sign()<0:
            raise ArithmeticError("executor produced an invalid probability")
        self.cache[key]=value
        return value


def packet(parameters,*,training_digest,view):
    parameters=_steps(parameters,5)
    if view not in VIEWS:raise ValueError("unknown feature view")
    if type(training_digest) is not str or len(training_digest)!=64 or any(c not in "0123456789abcdef" for c in training_digest):
        raise ValueError("training SHA-256 required")
    out=dict(schema="native-learning-model-v1",architecture=ARCHITECTURE,
             phase_steps=list(parameters),phase_unit="pi/32",feature_view=view,
             training_sha256=training_digest,execution="EXACT_CLASSICAL_SIMULATION",
             hardware_authorized=False,proof_status="NOT_A_MATHEMATICAL_PROOF")
    return dict(out,fingerprint=digest(out))


def load_packet(record):
    if type(record) is not dict:raise ValueError("model record required")
    try:
        expected=packet(record["phase_steps"],training_digest=record["training_sha256"],view=record["feature_view"])
    except (KeyError,TypeError) as error:raise ValueError("incomplete model record") from error
    if record!=expected:raise ValueError("model metadata or fingerprint mismatch")
    return tuple(expected["phase_steps"])


def fit(examples,*,view,evaluator=None,seeds=(17,41,73),sweeps=3,initial_parameters=None):
    """Train only on these examples; validation/test inputs are not arguments.

    Exact Brier-loss coordinate search on eight angles per coordinate. Strict
    improvements only; seeded restarts do not certify a global optimum.
    initial_parameters enables a declared warm start on a NEW training batch.
    """
    examples=_examples(examples)
    if view not in VIEWS:raise ValueError("unknown feature view")
    if any(e.view!=view for e in examples):raise ValueError("training feature view mismatch")
    _int(sweeps,"sweeps",1,8)
    if not isinstance(seeds,(tuple,list)) or not 1<=len(seeds)<=8:
        raise ValueError("1..8 declared restart seeds required")
    for seed in seeds:_int(seed,"seed",0,2**32-1)
    if initial_parameters is not None:initial_parameters=_steps(initial_parameters,5)
    evaluator=evaluator if evaluator is not None else Evaluator()
    if type(evaluator) is not Evaluator:raise ValueError("bounded Evaluator required")
    training_hash=digest([e.record() for e in examples]); objectives={};trace=[]
    grid=tuple(range(0,64,8)); best=None;best_loss=None
    def loss(params):
        if params not in objectives:
            evaluator.stats["objective_evaluations"]+=1
            errors=[evaluator.probability(e.features,params)-e.target for e in examples]
            objectives[params]=sum((error*error for error in errors),FIELD())/len(examples)
        return objectives[params]
    for restart,seed in enumerate(seeds):
        rng=random.Random(seed)
        params=initial_parameters if restart==0 and initial_parameters is not None else tuple(rng.choice(grid) for _ in range(5))
        value=loss(params)
        events=[dict(kind="initial",parameters=list(params),loss=value.to_dict())]
        stop="sweep_cap"
        for sweep in range(sweeps):
            changes=0
            for coordinate in range(5):
                candidate_best=params;candidate_loss=value
                for angle in grid:
                    candidate=params[:coordinate]+(angle,)+params[coordinate+1:]
                    proposed=loss(candidate)
                    if (proposed-candidate_loss).real_sign()<0:
                        candidate_best,candidate_loss=candidate,proposed
                if candidate_best!=params:
                    params,value=candidate_best,candidate_loss;changes+=1
                    events.append(dict(kind="accepted",sweep=sweep,coordinate=coordinate,
                                       parameters=list(params),loss=value.to_dict()))
            if not changes:stop="no_strict_coordinate_improvement";break
        trace.append(dict(seed=seed,stop=stop,events=events,final_parameters=list(params),final_loss=value.to_dict()))
        if best is None or (value-best_loss).real_sign()<0:best,best_loss=params,value
    return dict(schema="native-learning-fit-v1",model=packet(best,training_digest=training_hash,view=view),
                training_examples=len(examples),training_ids=[e.name for e in examples],
                selected_by="minimum_training_brier_loss_only",loss=best_loss.display(10),
                optimizer=dict(kind="classical_exact_coordinate_search",grid=list(grid),seeds=list(seeds),sweeps=sweeps),
                trace=trace,resources=dict(evaluator.stats),global_optimum_certified=False)


def assess(model,examples,*,evaluator=None):
    parameters=load_packet(model);examples=_examples(examples)
    if any(e.view!=model["feature_view"] for e in examples):raise ValueError("evaluation feature view mismatch")
    evaluator=evaluator if evaluator is not None else Evaluator()
    if type(evaluator) is not Evaluator:raise ValueError("bounded Evaluator required")
    rows=[];loss=FIELD();correct=0
    for e in examples:
        p=evaluator.probability(e.features,parameters)
        predicted=int((p-Q(1,2)).real_sign()>0)  # exact tie -> class zero
        correct+=predicted==e.target;error=p-e.target;loss+=error*error
        rows.append(dict(id=e.name,target=e.target,predicted=predicted,probability_one=p.display(10)))
    return dict(examples=len(examples),correct=correct,accuracy=str(Q(correct,len(examples))),
                brier_loss=(loss/len(examples)).display(10),predictions=rows,
                model_fingerprint=model["fingerprint"],dataset_sha256=digest([e.record() for e in examples]))


def information_ceiling(examples):
    """Best possible empirical accuracy for any predictor of these features."""
    examples=_examples(examples);counts={}
    if len({e.view for e in examples})!=1:raise ValueError("one declared feature view required")
    for e in examples:
        row=counts.setdefault(e.features,[0,0]);row[e.target]+=1
    return dict(distinct_inputs=len(counts),accuracy_ceiling=str(Q(sum(max(x) for x in counts.values()),len(examples))),
                conflicting_inputs=sum(all(x) for x in counts.values()),
                scope="finite supplied labelled dataset, including randomized quantum predictors")
