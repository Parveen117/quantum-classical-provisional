"""Construct and contract one exact MPS site at a time.

Controlled-gate history labels are shared across neighboring site plans. Site
factors are evaluated in their original local gate order; they need not coexist
in memory. This changes contraction scheduling, not bond rank or circuit physics.
"""
import numpy as np

from .dyadic import DONE, DZERO
from .exact import ZERO
from .factored import _gate, _contract_integer_site
from .integer_matrix import IntegerMatrix


def _plans(n, operations):
    plans = [[] for _ in range(n)]
    for name, qs in operations:
        if len(qs) == 1:
            plans[qs[0]].append((name, None, None))
            continue
        a,b = qs
        pairs = [('x',a,b),('x',b,a),('x',a,b)] if name == 'swap' else [(name[1:],a,b)]
        for basic, control, target in pairs:
            plans[control].append((basic, True, 1 if control < target else 0))
            plans[target].append((basic, False, 0 if control < target else 1))
    return plans


def _summaries(matrices, budget):
    counts, bounds = [], []
    for matrix in matrices:
        nonzero = np.zeros(matrix.shape, dtype=bool)
        bits = matrix.shift+1
        for part in matrix.parts:
            nonzero |= part != 0
            bits = max(bits, max((abs(v).bit_length() for v in part.flat), default=0))
        counts.append(int(np.count_nonzero(nonzero)))
        bounds.append(bits)
    bound = max(bounds,default=1)
    budget.stats['peak_site_coefficient_bit_bound'] = max(
        budget.stats.get('peak_site_coefficient_bit_bound',1),bound)
    # The raw shared denominator is a safe bound. If it exceeds the requested
    # cap, inspect canonical dyadics before deciding whether to reject.
    if bound > budget.max_bits:
        bound = max((v.max_bits for matrix in matrices for v in matrix.entries().values()),default=1)
    budget.inspect_summary(sum(counts),bound)
    return counts


def _apply_single(matrices, name, counts, budget):
    u = _gate(name)
    result = []
    for a in (0,1):
        out = None
        for b in (0,1):
            if u[a][b]:
                budget.tick(counts[b])
                term = matrices[b].scale(u[a][b])
                out = term if out is None else out.add(term)
        result.append(out)
    return result


def _interleave(even, odd, axis):
    shape = list(even.shape if even is not None else odd.shape)
    shape[axis] *= 2
    shift = max(matrix.shift for matrix in (even,odd) if matrix is not None)
    parts = tuple(np.zeros(tuple(shape),dtype=object) for _ in range(4))
    for bit, matrix in enumerate((even,odd)):
        if matrix is not None:
            selection = (slice(bit,None,2),slice(None)) if axis == 0 else (slice(None),slice(bit,None,2))
            for out, part in zip(parts,matrix.parts):
                out[selection] = part * (1 << (shift-matrix.shift))
    return IntegerMatrix(parts,shift)


def _site(plan, budget):
    matrices = [IntegerMatrix.from_sparse({(0,0):DONE},(1,1)),
                IntegerMatrix.from_sparse({},(1,1))]
    counts = _summaries(matrices,budget)
    for name, control, axis in plan:
        budget.emit('stream_site_gate_start')
        if control is None:
            matrices = _apply_single(matrices,name,counts,budget)
        else:
            shape = matrices[0].shape
            budget.bond(2*shape[axis])
            if 2*shape[0]*shape[1] > budget.max_coefficients:
                budget.fail('exact streaming site allocation exceeds coefficient-count budget')
            if control:
                matrices = [_interleave(matrices[0],None,axis),
                            _interleave(None,matrices[1],axis)]
            else:
                transformed = _apply_single(matrices,name,counts,budget)
                matrices = [_interleave(old,new,axis) for old,new in zip(matrices,transformed)]
        counts = _summaries(matrices,budget)
        budget.stats['local_factor_steps'] = budget.stats.get('local_factor_steps',0)+1
    return matrices, [bool(c) for c in counts]


def read(operations, factors, budget, *, reuse=True):
    plans = _plans(len(factors),operations)
    budget.stats.update(planned_forward_gates=len(operations),local_factor_steps=0,
                        site_factors_constructed=0,peak_live_site_factors=0,
                        coefficient_bit_statistic='safe shared-denominator bound; canonical check before rejection')
    boundary = IntegerMatrix.from_sparse({(0,0):DONE},(1,1))
    for plan, factor in zip(plans,factors):
        budget.emit('stream_site_start')
        matrices, nonempty = _site(plan,budget)
        budget.stats['site_factors_constructed'] += 1
        budget.stats['peak_live_site_factors'] = 1
        budget.emit('boundary_start')
        boundary = _contract_integer_site(boundary,matrices,nonempty,factor,budget,reuse=reuse)
        # Release the site before constructing its neighbor. Shared history
        # labels persist only in the contracted boundary matrix.
        del matrices
        budget.stats['contracted_sites'] += 1
        if boundary is None:
            return ZERO
    if boundary.shape != (1,1):
        raise ArithmeticError('streaming boundary did not close')
    value = boundary.entries().get((0,0),DZERO).to_exact()
    if value.c or value.d:
        raise ArithmeticError('Hermitian streaming readout acquired an imaginary value')
    return value
