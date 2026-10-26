"""Register family: the 2056-site design as one point of a parametric family.

A plan is (banks, width, workspace): N = banks*width + workspace sites on an
open nearest-neighbour chain. The exact cost laws, the chain counts and the
whole-register qualification families of DESIGN_2056.md are stated for every
N, and the existing stabilizer / clifford_t engines are run at a declared
bound instead of the historical constant. Carrier scaling compares the
single-photon path encoding with dual-rail encoding for the same N.

Nothing here manufactures qubits, proves efficient simulation of arbitrary
circuits or changes any engine's semantics; only the declared bound moves.
"""
from fractions import Fraction
import time

from .compact import _integer
from .exact import Exact, ONE, INV_SQRT2
from . import large_register
from . import stabilizer, clifford_t

DESIGN_2056 = dict(banks=64, width=32, workspace=8)
MAX_PLAN_SITES = large_register.REGISTER_BOUND_CEILING


def register_plan(banks, width, workspace):
    """Chain allocation and edge counts for N = banks*width + workspace."""
    banks = _integer(banks, 'banks', 1, MAX_PLAN_SITES)
    width = _integer(width, 'bank width', 1, MAX_PLAN_SITES)
    workspace = _integer(workspace, 'workspace', 0, MAX_PLAN_SITES)
    data = banks * width
    sites = data + workspace
    if sites > MAX_PLAN_SITES:
        raise ValueError('plan exceeds the register ceiling')
    within_banks = banks * (width - 1)
    between_banks = banks - 1
    within_workspace = max(workspace - 1, 0)
    data_to_workspace = 1 if workspace else 0
    edges = within_banks + between_banks + within_workspace + data_to_workspace
    assert edges == sites - 1
    return dict(banks=banks, width=width, workspace=workspace, data_sites=data, sites=sites,
                chain_edges=edges, edges_within_banks=within_banks, edges_between_banks=between_banks,
                edges_within_workspace=within_workspace, edges_data_to_workspace=data_to_workspace,
                bank_ranges=[(32 * 0 + b * width, b * width + width - 1) for b in range(banks)] if banks <= 4096 else None,
                hilbert_dimension_log2=sites)


def cost_laws(sites, *, chi_max=None):
    """Exact representation bounds from DESIGN_2056 section 4, for any N."""
    n = _integer(sites, 'sites', 1, MAX_PLAN_SITES)
    out = dict(sites=n, tableau_bits=2 * n * (2 * n + 1),
               tableau_mib=Fraction(2 * n * (2 * n + 1), 8 * 1024 * 1024),
               ghz_gates=n, ghz_schmidt_rank_every_cut=2 if n > 1 else 1)
    if chi_max is not None:
        chi = _integer(chi_max, 'chi_max', 1, 1 << 20)
        out['mps_coefficient_bound'] = 2 * n * chi * chi
    return out


def carrier_scaling(sites, encoding, *, bank_width=None):
    """Optical carrier counts for N two-level sites under a named encoding.

    single_photon_path: one photon, 2^N paths (the v0.9 exchange core scaled).
    dual_rail: N photons, 2N modes, one photon per site.
    banked_path: one photon per bank of `bank_width` sites, 2^width paths each.
    These are counting identities, not fabrication or loss budgets.
    """
    n = _integer(sites, 'sites', 1, MAX_PLAN_SITES)
    if encoding == 'single_photon_path':
        return dict(encoding=encoding, sites=n, photons=1, paths_log2=n,
                    paths=(1 << n) if n <= 64 else None, scalable=False)
    if encoding == 'dual_rail':
        return dict(encoding=encoding, sites=n, photons=n, modes=2 * n, scalable=True,
                    two_site_gate='needs photon-photon interference (HOM-class), not a single-photon MZI')
    if encoding == 'banked_path':
        w = _integer(bank_width, 'bank width', 1, 64)
        banks = -(-n // w)
        return dict(encoding=encoding, sites=n, bank_width=w, photons=banks,
                    paths_per_bank=1 << w, paths=banks * (1 << w), scalable=w <= 4)
    raise ValueError('unknown encoding')


def family_predictions(sites):
    """Symbolic answers of qualification families A and B for any N."""
    n = _integer(sites, 'sites', 1, MAX_PLAN_SITES)
    return dict(sites=n,
                A=dict(all_x_expectation=ONE, pair_zz_expectation=ONE, single_z_expectation=0,
                       two_site_00_marginal=Fraction(1, 2)),
                B=dict(all_x_expectation=INV_SQRT2, y0_x_rest_expectation=INV_SQRT2,
                       z_marginals='unchanged from A'))


def _ghz(n, phase=False):
    c = large_register.LargeCircuit(n).add('h', 0)
    for q in range(n - 1):
        c.add('cx', q, q + 1)
    if phase:
        c.add('t', 0)
    return c


def qualify_ghz(sites, *, with_phase=True):
    """Run families A and (optionally) B at N sites under a declared bound.

    The bound is raised for the call and restored afterwards. Returns exact
    pass/fail against the symbolic predictions plus wall-clock seconds.
    """
    n = _integer(sites, 'sites', 1, MAX_PLAN_SITES)
    previous = large_register.declare_register_bound(max(n, large_register.register_bound()))
    try:
        start = time.perf_counter()
        a = _ghz(n)
        all_x = stabilizer.expectation(a, {q: 'X' for q in range(n)}).value
        zz = stabilizer.expectation(a, {0: 'Z', n - 1: 'Z'}).value if n > 1 else ONE
        p00 = stabilizer.probability(a, {0: 0, n - 1: 0}).value if n > 1 else None
        seconds_a = time.perf_counter() - start
        result = dict(sites=n, family_a_passed=(all_x == ONE and zz == ONE and (n == 1 or p00 == Exact(Fraction(1, 2)))),
                      family_a_seconds=seconds_a, bound_used=large_register.register_bound())
        if with_phase:
            start = time.perf_counter()
            b = _ghz(n, True)
            bx = clifford_t.expectation(b, {q: 'X' for q in range(n)}, max_generators=min(n, 2056)).value
            by = clifford_t.expectation(b, {0: 'Y', **{q: 'X' for q in range(1, n)}}, max_generators=min(n, 2056)).value
            result.update(family_b_passed=(bx == INV_SQRT2 and by == INV_SQRT2),
                          family_b_seconds=time.perf_counter() - start)
        return result
    finally:
        large_register.declare_register_bound(previous)
