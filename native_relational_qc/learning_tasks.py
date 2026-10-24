"""Small, declared training tasks with exact native labels and fixed splits."""
from fractions import Fraction as Q
from itertools import product

from phase_seam_foundation.constitutive_response import CubicEnergy,response_record,patch_bound
from .self_learning import Example, digest, _int

MAGNITUDES={"train":(2,6),"validation":(4,),"test":(1,3,5,7)}


def xor_examples():
    return tuple(Example(f"xor_{a}{b}",(32*a,32*b),a^b,"xor_bits") for a,b in product(range(2),repeat=2))


def curvature_case(u,v,*,view="first_layer"):
    _int(u,"u",-7,7);_int(v,"v",-7,7)
    if not u or not v:raise ValueError("zero-curvature boundary excluded from this binary task")
    if view not in ("first_layer","point_only"):raise ValueError("unknown curvature feature view")
    energy=CubicEnergy((2,1,5),(u,0,0,v),(10,-10))
    record=response_record(energy)
    # A source-generated finite patch, not merely an arbitrary label matrix.
    bounds=patch_bound(energy,(0,0),patch_radius=Q(1,20),force_radius=0)
    if view=="first_layer":
        observed=(record["hessian_first"][0][0][0],record["hessian_first"][1][1][1])
    else:
        observed=(record["responses"]["lambdaV"],record["responses"]["lambdaS"])
    phases=tuple(16+2*x for x in observed)
    if any(x.denominator!=1 for x in phases):raise ValueError("task encoding requires exact integer steps")
    curvature=record["selected_response_curvature"]
    example=Example(f"curvature_u{u}_v{v}",tuple(int(x) for x in phases),int(curvature<0),view)
    source=dict(u=u,v=v,energy=energy.specification(),
                six_point_responses={k:str(v) for k,v in record["responses"].items()},
                observed_features=[str(x) for x in observed],curvature=str(curvature),
                positive_patch_radius="1/20",patch_lower_eigenvalue=str(bounds["patch_lower_eigenvalue"]))
    return example,source


def curvature_splits(*,view="first_layer"):
    splits={};source={}
    for name,magnitudes in MAGNITUDES.items():
        examples=[]
        values=tuple(sign*m for m in magnitudes for sign in (-1,1))
        for u,v in product(values,repeat=2):
            example,record=curvature_case(u,v,view=view)
            examples.append(example);source[example.name]=record
        splits[name]=tuple(examples)
    return splits,dict(schema="native-curvature-task-v1",feature_view=view,
         label="one iff selected native response curvature is negative",
         inputs="first Hessian layer" if view=="first_layer" else "two of six identical point responses",
         split_rule={k:list(v) for k,v in MAGNITUDES.items()},
         test_magnitudes_absent_from_training=True,validation_used_for_selection=False,
         declared_models=True,physical_measurements=False,source_records=source,
         split_hashes={k:digest([e.record() for e in rows]) for k,rows in splits.items()})


def classical_baselines(training,testing):
    """Exact same-feature linear least squares and a one-coefficient product fit.

    On this fixed balanced Cartesian design, the OLS target has zero mean and
    zero correlations with u and v. This is a baseline for this task, not a
    theorem that every possible linear classifier must attain exactly 50%.
    """
    def raw(e):return tuple(Q(x-16,2) for x in e.features)
    if not training or not testing:raise ValueError("nonempty training and evaluation sets required")
    if any(e.view!="first_layer" for e in (*training,*testing)):
        raise ValueError("classical comparison requires the same first-layer features")
    moments=[sum(Q(1-2*e.target)*(Q(1),*raw(e))[j] for e in training) for j in range(3)]
    if any(moments):raise ValueError("this analytic OLS baseline requires the declared balanced training design")
    numerator=sum(raw(e)[0]*raw(e)[1]*(1-2*e.target) for e in training)
    denominator=sum((raw(e)[0]*raw(e)[1])**2 for e in training)
    if not denominator:raise ValueError("product feature has zero training norm")
    coefficient=numerator/denominator
    linear_correct=sum(e.target==0 for e in testing)
    product_correct=sum(int(coefficient*raw(e)[0]*raw(e)[1]<0)==e.target for e in testing)
    return dict(linear_ols=dict(coefficients=["0","0","0"],accuracy=str(Q(linear_correct,len(testing)))),
                product_regression=dict(coefficient=str(coefficient),accuracy=str(Q(product_correct,len(testing))),
                    trainable_parameters=1,feature="u*v",training_examples=len(training)),
                no_quantum_advantage_established=True)
