"""Exact matrix products with signed reuse and bounded integer limbs.

Only zero vectors and vectors equal up to a real sign are identified. This is
an algebraic factorization of one matrix product, not numerical rank truncation.
Binary64 dot products contain only integers under a proved exactness bound; reconstruction
and field reduction use arbitrary-precision Python integers. Quantum coefficients
are never approximated; the float instructions evaluate bounded integer sums.
"""
from __future__ import annotations

import numpy as np


def _row_groups(parts):
    """Return representative rows, their signs, and each source row's map."""
    representatives, signs, mapping, lookup = [], [], [], {}
    for row in range(parts[0].shape[0]):
        key = tuple(int(v) for part in parts for v in part[row])
        first = next((v for v in key if v), 0)
        if not first:
            mapping.append(None)
            continue
        sign = 1 if first > 0 else -1
        key = tuple(sign*v for v in key)
        if key not in lookup:
            lookup[key] = len(representatives)
            representatives.append(row)
            signs.append(sign)
        mapping.append((lookup[key], sign))
    return representatives, signs, mapping


def _limbs(matrix, width):
    mask = (1 << width)-1
    bits = max((abs(int(v)).bit_length() for v in matrix.flat), default=0)
    result = []
    for shift in range(0, bits, width):
        chunk = np.array([((abs(int(v)) >> shift) & mask) * (-1 if v < 0 else 1)
                          for v in matrix.flat], dtype=np.float64).reshape(matrix.shape)
        if np.any(chunk):
            result.append((shift, chunk))
    return result


def _limb_product(left, right, budget):
    """Multiply four numerator channels; all intermediate integer dot sums are exact in binary64."""
    m, k = left[0].shape
    n = right[0].shape[1]
    if np.finfo(np.float64).nmant != 52:
        raise RuntimeError('exact limb kernel requires IEEE binary64 precision')
    budget.stats['integer_limb_backend'] = 'numpy_binary64_bounded_exact_integers'
    # k <= 2**ceil(log2(k)), and 2*width+ceil(log2(k)) <= 52.
    # Hence every partial signed dot sum has absolute value < 2**52, hence exactly representable in binary64.
    width = (52-(k-1).bit_length())//2
    if width < 1:
        raise ValueError('inner dimension exceeds bounded integer kernel')
    bound = k*((1 << width)-1)**2
    if bound >= (1 << 53):
        raise ArithmeticError('binary64 integer-dot bound violated before multiplication')
    budget.stats['peak_integer_partial_sum_bound'] = max(
        budget.stats.get('peak_integer_partial_sum_bound', 0), bound)
    budget.stats['minimum_limb_bits'] = min(budget.stats.get('minimum_limb_bits', width), width)
    left_chunks = [_limbs(part, width) for part in left]
    right_chunks = [_limbs(part, width) for part in right]
    out = tuple(np.zeros((m,n), dtype=object) for _ in range(4))
    # Multiplication in basis [1, sqrt(2), i, i*sqrt(2)].
    table = (((0,1),(1,1),(2,1),(3,1)),
             ((1,1),(0,2),(3,1),(2,2)),
             ((2,1),(3,1),(0,-1),(1,-1)),
             ((3,1),(2,2),(1,-1),(0,-2)))
    for a, chunks_a in enumerate(left_chunks):
        for b, chunks_b in enumerate(right_chunks):
            channel, factor = table[a][b]
            for shift_a, chunk_a in chunks_a:
                for shift_b, chunk_b in chunks_b:
                    product = chunk_a @ chunk_b
                    if (not np.all(np.isfinite(product)) or np.any(np.abs(product) > bound)
                            or np.any(product != np.trunc(product))):
                        raise ArithmeticError('bounded integer dot product violated its exactness contract')
                    budget.stats['exact_limb_products'] = budget.stats.get('exact_limb_products', 0)+1
                    out[channel][:] += product.astype(np.int64).astype(object) * (factor << (shift_a+shift_b))
    return out


def multiply(left, right, budget):
    """Compute left @ right exactly, reusing signed equal vectors.

    The caller supplies four integer numerator matrices per operand. Shared
    dyadic denominators are unchanged by this operation and handled by the caller.
    """
    m,k = left[0].shape
    k2,n = right[0].shape
    if k != k2:
        raise ValueError('matrix product shape mismatch')
    if max(m*k,k*n,m*n) > budget.max_coefficients:
        budget.fail('exact reused matrix allocation exceeds coefficient-count budget')
    budget.stats['unreused_matrix_product_slots'] = budget.stats.get('unreused_matrix_product_slots',0)+m*k*n
    # R = S R_unique, so L R = (L S) R_unique. S contains only 0,+1,-1.
    indices, signs, mapping = _row_groups(right)
    r = len(indices)
    reduced_right = tuple(part[indices,:] * np.array(signs,dtype=object)[:,None] for part in right)
    reduced_left = tuple(np.zeros((m,r),dtype=object) for _ in range(4))
    for j, entry in enumerate(mapping):
        if entry is not None:
            target, sign = entry
            for out, part in zip(reduced_left,left):
                out[:,target] += sign*part[:,j]
    # An exact cancellation in L S makes the corresponding inner label unused.
    active = [j for j in range(r) if any(np.any(part[:,j]) for part in reduced_left)]
    reduced_left = tuple(part[:,active] for part in reduced_left)
    reduced_right = tuple(part[active,:] for part in reduced_right)
    budget.stats['reused_inner_labels'] = budget.stats.get('reused_inner_labels',0)+k-len(active)
    row_indices, row_signs, row_map = _row_groups(reduced_left)
    col_indices, col_signs, col_map = _row_groups(tuple(p.T for p in reduced_right))
    a = tuple(part[row_indices,:] * np.array(row_signs,dtype=object)[:,None] for part in reduced_left)
    b = tuple(part[:,col_indices] * np.array(col_signs,dtype=object)[None,:] for part in reduced_right)
    actual = len(row_indices)*len(active)*len(col_indices)
    budget.tick(actual)
    budget.stats['reused_matrix_product_slots'] = budget.stats.get('reused_matrix_product_slots',0)+actual
    budget.stats['reused_outer_rows'] = budget.stats.get('reused_outer_rows',0)+m-len(row_indices)
    budget.stats['reused_outer_columns'] = budget.stats.get('reused_outer_columns',0)+n-len(col_indices)
    budget.stats['reused_integer_matrix_products'] = budget.stats.get('reused_integer_matrix_products',0)+1
    if not actual:
        return tuple(np.zeros((m,n),dtype=object) for _ in range(4))
    contracted = _limb_product(a,b,budget)
    rows = np.array([v[0] if v is not None else 0 for v in row_map])
    columns = np.array([v[0] if v is not None else 0 for v in col_map])
    rs = np.array([v[1] if v is not None else 0 for v in row_map],dtype=object)
    cs = np.array([v[1] if v is not None else 0 for v in col_map],dtype=object)
    return tuple(part[np.ix_(rows,columns)] * rs[:,None] * cs[None,:] for part in contracted)
