"""Certify phase-seam ledger claims with the calculator's own exact backend.

The phase-seam programme (phase_seam_foundation) proves its cluster-state
claims with a small private engine over Q(zeta_64), because the calculator had
no mid-circuit measurement with pi/32 phases. This module re-derives the
v0.29 cluster witness on the calculator's flat `cyclotomic_pow2` backend,
using static circuits instead of the separate measurement-pattern engine.
The integrated route shares flat arithmetic; the circuit/readout constructions
are independent, not the arithmetic implementations. A
certificate is granted only when every exact value agrees and every negative
control fails as it must; otherwise the grade is MISMATCH or INCOMPLETE and
the record says where.

Static reduction (the one-way-model byproduct identity, checked here through
the calculator in `measurement_identity`): applying X^x Z^z to a node and then
measuring it in the X-Y plane at angle a with outcome s has the same
probability as measuring the uncorrected node at angle (-1)^x a with outcome
s XOR z. In the classifier pattern the X parity of a node is the outcome of
its unique flow predecessor, so the 512 corrected outcome paths of a case fall
into 64 static circuits, one per sign assignment of the six nodes that have a
predecessor; one distribution query over the ten measured wires per circuit
gives every path probability and every conditional readout exactly.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path

from .calculator import calculate
from .ledger_certify import certify, EXPECTED

CERTIFY_SCHEMA = 'nrqc-certificate-v1'
GRADES = ('CERTIFIED', 'MISMATCH', 'INCOMPLETE')
BACKEND = 'cyclotomic_pow2'
ORDER_M = 64                      # measurement angles are multiples of pi/32 = 2*pi/64

# Angle k*pi/32 as diag(1, zeta_64^k) through the calculator's own gate names.
_PHASE_BITS = (('p64', 1), ('p32', 2), ('p16', 4), ('t', 8), ('s', 16), ('z', 32))


def phase_steps(operations, qubit, steps):
    """Append gates realising diag(1, exp(2*pi*i*steps/64)) on one wire."""
    steps %= ORDER_M
    for name, weight in _PHASE_BITS:
        if steps & weight:
            operations.append([name, [qubit]])


def measure_in_plane(operations, qubit, angle):
    """Rotate so that a Z-basis reading of `qubit` is the X-Y plane measurement at `angle`.

    Outcome s projects onto (|0> + (-1)^s e^{i angle}|1>)/sqrt(2), the convention of
    phase_seam_foundation.cluster_compile._State.measure.
    """
    phase_steps(operations, qubit, -angle)
    operations.append(['h', [qubit]])


def flat_field():
    from .cyclotomic_pow2 import field_of_order
    return field_of_order(ORDER_M)


def exact_value(exact):
    """The calculator's exact value, lifted into the flat field Q(zeta_64).

    The calculator works in the smallest power-of-two order the gates need; a
    value in Q(zeta_M) is lifted by zeta_M = zeta_64^(64/M).
    """
    import re
    from .cyclotomic_pow2 import field_of_order
    order = int(re.search(r'Q\(zeta_(\d+)\)', exact['basis']).group(1))
    if order > ORDER_M or ORDER_M % order:
        raise ValueError(f'value in Q(zeta_{order}) does not embed in Q(zeta_{ORDER_M})')
    value = field_of_order(order).from_dict(exact)
    F = flat_field()
    lifted = sum((F.root(e * (ORDER_M // order)) * c for e, c in value.terms), F())
    return lifted * Fraction(1, value.den)


def embed_tower(value):
    """Embed a phase_seam_foundation value (the nested Q(zeta_64) tower) into the flat field.

    Cyclotomic64 = lo + hi*u, Cyclotomic32 = lo + hi*w, Cyclotomic = lo + hi*z with
    u = zeta_64, w = zeta_64^2, z = zeta_64^4, and the lowest level is the EMK field
    Q(sqrt(2), i), which the flat field constructs directly.
    """
    from .exact import Exact
    from .cyclotomic import Cyclotomic
    from .cyclotomic32 import Cyclotomic32
    from .cyclotomic64 import Cyclotomic64
    F = flat_field()
    from .cyclotomic_pow2 import CyclotomicPow2
    if isinstance(value, CyclotomicPow2):
        return F(value)
    if isinstance(value, Exact):
        return F(value)
    step = {Cyclotomic64: 1, Cyclotomic32: 2, Cyclotomic: 4}[type(value)]
    return embed_tower(value.lo) + embed_tower(value.hi) * F.root(step)


def _text(value):
    """Exact value as text: the rational when it is one, else the certified decimal and the field element."""
    data = value.to_dict()
    rows = data.get('real_numerators')
    if rows is not None and not any(rows[1:]):
        return str(Fraction(rows[0] if rows else 0, int(data['denominator'])))
    return dict(decimal=value.display(12)['decimal'], exact=data)


def _run(n_qubits, operations, queries, max_branches=65_536):
    document = dict(schema='nrqc-calculator-v1', n_qubits=n_qubits, operations=operations,
                    backend=BACKEND, decimal_places=12,
                    limits=dict(max_branches=max_branches, max_work=1_000_000_000), queries=queries)
    report = calculate(document)
    if report['status'] != 'completed':
        raise RuntimeError('calculator did not complete: ' + json.dumps(
            [a.get('error') for a in report['answers'] if a.get('status') != 'completed']))
    return report


def probabilities(n_qubits, operations, outcome_maps):
    """Exact probabilities (flat-field elements) of several Z-basis outcome patterns on one prepared circuit."""
    report = _run(n_qubits, operations,
                  [dict(id=f'q{i}', kind='probability', outcomes=m) for i, m in enumerate(outcome_maps)])
    return [exact_value(a['value']['exact']) for a in report['answers']]


def distribution(n_qubits, operations, wires):
    """Exact joint distribution over `wires`; keys are bitstrings in the order of `wires`."""
    report = _run(n_qubits, operations, [dict(id='d', kind='distribution', qubits=list(wires))])
    answer = report['answers'][0]
    assert answer['bitstring_qubits_left_to_right'] == list(wires)
    return {label: exact_value(v['exact']) for label, v in answer['probabilities'].items()}, report


def measurement_identity():
    """Byproduct identity on one qubit, exactly, through the calculator.

    For each state in a small exact family, every eighth angle, each byproduct
    (x, z) and outcome s: P(s | X^x Z^z then measure at a) equals
    P(s XOR z | measure at (-1)^x a).
    """
    checks = 0
    preparations = ([], [['h', [0]]], [['h', [0]], ['t', [0]]], [['h', [0]], ['p64', [0]], ['s', [0]]],
                    [['h', [0]], ['p32', [0]], ['p64', [0]], ['sx', [0]]])
    for prep in preparations:
        for a in range(0, ORDER_M, 7):
            for x in (0, 1):
                for z in (0, 1):
                    corrected = list(prep) + ([['x', [0]]] if x else []) + ([['z', [0]]] if z else [])
                    measure_in_plane(corrected, 0, a)
                    plain = list(prep)
                    measure_in_plane(plain, 0, -a if x else a)
                    for s in (0, 1):
                        left = probabilities(1, corrected, [{'0': s}])[0]
                        right = probabilities(1, plain, [{'0': s ^ z}])[0]
                        if left != right:
                            return dict(holds=False, checks=checks, failed=dict(prep=prep, angle=a, x=x, z=z, s=s))
                        checks += 1
    return dict(holds=True, checks=checks)


# ------------------------------------------------------------------ the cluster witness

def _spec(features, parameters):
    from phase_seam_foundation import cluster_compile as cc
    spec = cc.pattern(features, parameters)
    predecessor = {v: k for k, v in spec['flow'].items()}
    measured = list(spec['order']) + [spec['readout']]
    signed = [n for n in measured if n in predecessor]        # nodes whose angle sign a path can flip
    spec.update(predecessor=predecessor, measured=measured, signed=signed)
    return spec


def cluster_operations(spec, flips):
    """The cluster, then every measured node rotated into its (sign-adapted) basis.

    `flips` maps a node to 1 when the path gives it an X byproduct, negating its angle.
    """
    operations = [['h', [q]] for q in range(spec['nodes'])]
    for a, b in spec['edges']:
        operations.append(['cz', [a, b]])
    for node in spec['measured']:
        angle = spec['measurement_angles'][node]
        measure_in_plane(operations, node, -angle if flips.get(node) else angle)
    return operations


def paths_for_assignment(spec, assignment):
    """All corrected outcome paths whose X byproducts realise `assignment` on the signed nodes."""
    order, predecessor = spec['order'], spec['predecessor']
    free = [n for n in order if n not in {predecessor[s] for s in spec['signed']}]
    out = []
    for bits in range(1 << len(free)):
        path = {}
        for i, n in enumerate(free):
            path[n] = (bits >> i) & 1
        for s, value in zip(spec['signed'], assignment):
            path[predecessor[s]] = value
        out.append(tuple(path[n] for n in order))
    return out


def path_byproducts(spec, path):
    """X and Z parities every node carries at its measurement, for one corrected path."""
    x_par = {n: 0 for n in range(spec['nodes'])}
    z_par = {n: 0 for n in range(spec['nodes'])}
    for s, node in zip(path, spec['order']):
        if s:
            c = spec['corrections'][node]
            x_par[c['x']] ^= 1
            for w in c['z']:
                z_par[w] ^= 1
    return x_par, z_par


def cluster_assignment(features, parameters, assignment):
    """One static circuit (one sign assignment) and the exact facts of its eight paths."""
    spec = _spec(features, parameters)
    flips = dict(zip(spec['signed'], assignment))
    started = time.perf_counter()
    dist, report = distribution(spec['nodes'], cluster_operations(spec, flips), spec['measured'])
    readout_index = spec['measured'].index(spec['readout'])
    rows = []
    for path in paths_for_assignment(spec, assignment):
        x_par, z_par = path_byproducts(spec, path)
        assert all(x_par[n] == flips[n] for n in spec['signed'])
        raw = {n: s ^ z_par[n] for s, n in zip(path, spec['order'])}
        label = lambda readout_bit: ''.join(str(raw[n]) if n != spec['readout'] else str(readout_bit)
                                            for n in spec['measured'])
        p0, p1 = dist[label(0)], dist[label(1)]
        p_path = p0 + p1
        # corrected readout 1 == raw readout 1 XOR z on the readout node
        p_one = p1 if not z_par[spec['readout']] else p0
        rows.append(dict(path=''.join(map(str, path)), path_probability=p_path,
                         readout_probability=None if not p_path else p_one * _as_rational(p_path) ** -1))
    answer = report['answers'][0]
    work = answer.get('statistics', {}).get('work_used') or answer.get('statistics', {}).get('work_totals', {}).get('work_used')
    return dict(assignment=''.join(map(str, assignment)), rows=rows, seconds=round(time.perf_counter() - started, 3),
                distribution_sums_to_one=sum(dist.values(), flat_field()()) == flat_field()(1), calculator_work_used=work)


def _as_rational(value):
    """A flat-field element that must be rational, as a Fraction."""
    data = value.to_dict()
    rows = data.get('real_numerators')
    if rows is None or any(rows[1:]):
        raise ArithmeticError('a path probability must be rational')
    return Fraction(rows[0] if rows else 0, int(data['denominator']))


def _assignment_job(args):
    """Worker entry: field elements travel between processes as their exact dicts."""
    features, parameters, assignment = args
    block = cluster_assignment(features, parameters, assignment)
    for row in block['rows']:
        row['path_probability'] = row['path_probability'].to_dict()
        row['readout_probability'] = None if row['readout_probability'] is None else row['readout_probability'].to_dict()
    return block


def _revive(block):
    for row in block['rows']:
        row['path_probability'] = exact_value(row['path_probability'])
        row['readout_probability'] = None if row['readout_probability'] is None else exact_value(row['readout_probability'])
    return block


def cluster_witness(features, parameters, assignments='all', *, workers=1):
    """Re-derive the classifier cluster witness of phase seam v0.29 on the calculator.

    Every corrected path must have probability exactly 2^-9 and conditional
    readout probability exactly equal to the circuit probability; the pattern
    engine of cluster_compile must give the same number.
    """
    from phase_seam_foundation import cluster_compile as cc
    spec = _spec(features, parameters)
    circuit_probability = embed_tower(cc.circuit_probability(features, parameters))
    count = len(spec['signed'])
    if assignments == 'all':
        assignment_list = [tuple((k >> i) & 1 for i in range(count)) for k in range(1 << count)]
    else:
        assignment_list = [tuple(a) for a in assignments]
    jobs = [(list(features), list(parameters), a) for a in assignment_list]
    started = time.perf_counter()
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            blocks = [_revive(b) for b in pool.map(_assignment_job, jobs)]
    else:
        blocks = [_revive(_assignment_job(j)) for j in jobs]
    expected_weight = flat_field()(Fraction(1, 1 << len(spec['order'])))
    rows = [r for b in blocks for r in b['rows']]
    mismatches = [r['path'] for r in rows if r['path_probability'] != expected_weight or r['readout_probability'] != circuit_probability]
    run = cc.pattern_run(features, parameters, rule='flow')
    pattern_value = None if run['readout_probability'] is None else embed_tower(run['readout_probability'])
    return dict(features=list(features), parameters=list(parameters),
                circuit_probability=_text(circuit_probability),
                assignments_requested=len(assignment_list), assignments_checked=len(blocks),
                paths_checked=len(rows), paths_total=1 << len(spec['order']),
                every_path_weight_exact=all(r['path_probability'] == expected_weight for r in rows),
                every_distribution_normalised=all(b['distribution_sums_to_one'] for b in blocks),
                mismatching_paths=mismatches,
                pattern_engine=dict(witness=run['witness'], readout_probability=None if pattern_value is None else _text(pattern_value),
                                    agrees_with_calculator=pattern_value == circuit_probability),
                seconds=round(time.perf_counter() - started, 3),
                assignments=[dict(b, rows=[dict(r, path_probability=_text(r['path_probability']),
                                                 readout_probability=None if r['readout_probability'] is None else _text(r['readout_probability']))
                                            for r in b['rows']]) for b in blocks])


def control_without_corrections(features, parameters):
    """Negative control: with the byproducts ignored, some outcome paths give a different readout.

    One distribution of the cluster measured at the nominal angles is read for
    all 512 paths as if no correction were applied. The control passes when at
    least one path's conditional readout differs from the circuit probability,
    so the corrections are doing work. (Comparing only the all-zero and all-one
    paths is not a valid control at Clifford angles, where those two can agree.)
    """
    from phase_seam_foundation import cluster_compile as cc
    spec = _spec(features, parameters)
    circuit_probability = embed_tower(cc.circuit_probability(features, parameters))
    dist, _ = distribution(spec['nodes'], cluster_operations(spec, {}), spec['measured'])
    differing, total, distinct = 0, 0, set()
    for bits in range(1 << len(spec['order'])):
        raw = {n: (bits >> i) & 1 for i, n in enumerate(spec['order'])}
        label = lambda bit: ''.join(str(raw[n]) if n != spec['readout'] else str(bit) for n in spec['measured'])
        p0, p1 = dist[label(0)], dist[label(1)]
        if not (p0 + p1):
            continue
        value = p1 * _as_rational(p0 + p1) ** -1
        total += 1
        distinct.add(json.dumps(value.to_dict(), sort_keys=True))
        if value != circuit_probability:
            differing += 1
    return dict(paths_with_weight=total, paths_differing_from_circuit=differing,
                distinct_readout_values=len(distinct), corrections_do_work=differing > 0)


def default_cases():
    from phase_seam_foundation import cluster_compile as cc, cluster_noise as cn
    cases = [dict(label='generic', features=list(cn.GENERIC['features']), parameters=list(cn.GENERIC['parameters']))]
    cases += [dict(label=f'xor_{a}{b}', features=[32 * a, 32 * b], parameters=list(cc.XOR_CHECKPOINT)) for a in (0, 1) for b in (0, 1)]
    return cases


def certify_cluster(cases=None, assignments='all', *, workers=1, identity=True):
    from phase_seam_foundation import cluster_compile as cc
    cases = default_cases() if cases is None else cases
    if not cases:raise ValueError('at least one declared case is required')
    identity_record = measurement_identity() if identity else dict(holds=None, checks=0, skipped=True)
    results = []
    for case in cases:
        witness = cluster_witness(case['features'], case['parameters'], assignments, workers=workers)
        witness['label'] = case['label']
        witness['control_without_corrections'] = control_without_corrections(case['features'], case['parameters'])
        results.append(witness)
    complete = identity and all(r['assignments_checked'] == (1 << 6) for r in results)
    mismatch = identity_record['holds'] is False or any(
        r['mismatching_paths'] or not r['every_path_weight_exact'] or not r['every_distribution_normalised']
        or not r['pattern_engine']['agrees_with_calculator'] or not r['control_without_corrections']['corrections_do_work']
        for r in results)
    grade = 'MISMATCH' if mismatch else ('CERTIFIED' if complete else 'INCOMPLETE')
    return dict(schema=CERTIFY_SCHEMA, backend=BACKEND, grade=grade,
                claim='phase seam v0.29 cluster witness: on every corrected outcome path the readout probability equals the circuit probability, and every path has weight 2^-9',
                measurement_identity=identity_record, cases=results,
                claim_boundary=['ideal lossless cluster; loss, multi-pair emission and detector noise are outside this certificate',
                                'agreement of two circuit/readout constructions with shared exact arithmetic; no hardware observation',
                                'CERTIFIED requires the identity check and all 64 sign assignments (512 paths) of every case; '
                                'MISMATCH records any exact disagreement or a failed control'],
                never_granted=list(cc.NEVER_GRANTED))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != 'cluster':
        from .ledger_certify import main as ledger_main
        return ledger_main(argv[1:] if argv and argv[0]=='ledger' else argv)
    parser = argparse.ArgumentParser(prog='nrqc certify', description=__doc__)
    parser.add_argument('claim', choices=['cluster'])
    parser.add_argument('--assignments', default='all', help="'all' (64 per case) or an integer count of leading assignments")
    parser.add_argument('--cases', default='all', help="'all' or a comma-separated subset of generic,xor_00,xor_01,xor_10,xor_11")
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    assignments = 'all'
    if args.assignments != 'all':
        count = int(args.assignments)
        if not 1 <= count <= 64:parser.error('--assignments must be 1..64 or all')
        assignments = [tuple((k >> i) & 1 for i in range(6)) for k in range(count)]
    cases = default_cases()
    if args.cases != 'all':
        wanted = set(args.cases.split(','))
        if not wanted <= {c['label'] for c in cases}:parser.error('unknown cluster case')
        cases = [c for c in cases if c['label'] in wanted]
    if not 1 <= args.workers <= 8:parser.error('--workers must be 1..8')
    result = certify_cluster(cases, assignments, workers=args.workers)
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if args.out:
        args.out.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if result['grade'] == 'CERTIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
