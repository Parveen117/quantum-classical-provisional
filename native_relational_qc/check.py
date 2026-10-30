"""Report which calculator backends accept a request, without executing it.

The calculator never switches backend on its own. This module answers the
question a user otherwise discovers by trial: given one JSON request, which
explicit backends accept its width, gate alphabet, query kinds and options,
and why do the others reject it. Acceptance here is the same static
validation the calculator runs before execution; it does not predict whether
the execution budget will be met.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .calculator import INPUT_SCHEMA, MAX_INPUT_BYTES, LIMIT_RANGES, loads, validate

CHECK_SCHEMA = 'nrqc-check-v1'

BACKENDS = ('factored', 'observer', 'stabilizer', 'clifford_t', 'clifford_frame',
            'jya_frame', 'cyclotomic', 'cyclotomic32', 'cyclotomic64',
            'cyclotomic_pow2', 'observer32')

_SINGLE = 'id x y z h s sdg t tdg sx sxdg r k rk'
_CONTROLLED = 'cx cz ch cs ct swap ccx'
_CLIFFORD = 'id x y z h s sdg sx sxdg r k rk cx cz swap'

# Static capability table. Width and gate alphabets are read from the circuit
# classes each backend validates with; limits are the calculator defaults.
CAPABILITIES = {
    'factored': dict(
        width='1..256', gates=f'{_SINGLE}; adjacent cx cz ch cs ct swap',
        queries='probability expectation distribution geometry',
        options='simplify, contraction (integer sparse reuse streaming)',
        limits='max_bond 256, max_coefficients 1e6',
        representation='product observer plus exact sparse MPS contraction',
        notes='default backend; nonadjacent two-site gates and ccx are rejected'),
    'observer': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED} (any sites)',
        queries='probability expectation distribution geometry',
        options='simplify',
        limits='max_terms 1e5',
        representation='expanded exact Pauli observer',
        notes='term growth bounds depth; see STRESS_BENCHMARK.md'),
    'stabilizer': dict(
        width='1..2056 (declared bound)', gates=_CLIFFORD,
        queries='probability expectation distribution geometry',
        options='simplify',
        limits='max_generators 2056',
        representation='bit-packed Pauli pullback, generator elimination',
        notes='Clifford only; t, tdg, ch, cs, ct, ccx rejected'),
    'clifford_t': dict(
        width='1..2056 (declared bound)', gates=f'{_CLIFFORD} t tdg',
        queries='probability expectation distribution geometry',
        options='simplify',
        limits='max_terms 1e5',
        representation='Pauli pullback with bounded exact T expansion',
        notes='ch, cs, ct, ccx rejected'),
    'clifford_frame': dict(
        width='1..2056 (declared bound)', gates=f'{_CLIFFORD} t tdg',
        queries='probability expectation distribution geometry',
        options='simplify',
        limits='max_generators 2056, max_branches 4096, max_pairs 1e6',
        representation='retained Clifford circuit plus sparse residual vector',
        notes='no initial 2^k projector enumeration'),
    'jya_frame': dict(
        width='1..2056 (declared bound)', gates=f'{_CLIFFORD} t tdg',
        queries='probability expectation distribution geometry',
        options='simplify',
        limits='max_generators 2056, max_branches 4096, max_pairs 1e6',
        representation='clifford_frame with exact trace/determinant recurrence on repeated single-qubit words',
        notes='same alphabet and limits as clifford_frame'),
    'cyclotomic': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED}; p16 p16dg cp16 cp16dg',
        queries='probability expectation distribution (1..8 wires)',
        options='none (simplify and contraction rejected)',
        limits='max_branches 4096',
        representation='sparse amplitudes in Q(zeta_16), one preparation per batch',
        notes='geometry not implemented'),
    'cyclotomic32': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED}; p16 p32 and dg/cp forms',
        queries='probability expectation distribution (1..8 wires)',
        options='none',
        limits='max_branches 4096',
        representation='sparse amplitudes in Q(zeta_32)',
        notes='geometry not implemented'),
    'cyclotomic64': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED}; p16 p32 p64 and dg/cp forms',
        queries='probability expectation distribution (1..8 wires)',
        options='none',
        limits='max_branches 4096',
        representation='sparse amplitudes in Q(zeta_64)',
        notes='geometry not implemented'),
    'cyclotomic_pow2': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED}; pK pKdg cpK cpKdg for every power of two 2<=K<=4096',
        queries='probability expectation distribution (1..12 wires, up to 4096 scalar evaluations)',
        options='readout_workers 1..8',
        limits='max_branches 4096 (ceiling 1048576), 1e6 declared gates',
        representation='flat Q(zeta_M), sparse/dense exact product, M = largest K used',
        notes='supersedes cyclotomic, cyclotomic32, cyclotomic64; geometry not implemented'),
    'observer32': dict(
        width='1..256', gates=f'{_SINGLE}; {_CONTROLLED}; p16 p32 and dg/cp forms',
        queries='probability expectation distribution (1..8 wires)',
        options='none',
        limits='max_terms 4096',
        representation='measurement pullback in Q(zeta_32) without amplitude preparation',
        notes='geometry not implemented'),
}


def _requested(document):
    if not isinstance(document, dict):
        raise ValueError('calculator request must be a JSON object')
    if document.get('schema') != INPUT_SCHEMA:
        raise ValueError('unsupported calculator input schema')
    backend = document.get('backend', 'factored')
    if backend not in BACKENDS:
        raise ValueError('unknown backend; select an explicit supported backend, with no implicit fallback')
    return backend


def check(document):
    """Validate one request against every backend and report the outcome.

    The result lists accepted backends with the limits that would apply, and
    rejected backends with the calculator's own rejection message. Only the
    `contraction` option is dropped when probing non-factored backends, since
    it is defined for the factored backend alone; the drop is recorded.
    """
    requested = _requested(document)
    rows = []
    for backend in BACKENDS:
        probe = dict(document)
        probe['backend'] = backend
        dropped = []
        if backend != 'factored' and 'contraction' in probe:
            probe.pop('contraction')
            dropped.append('contraction')
        alphabet=set((_CLIFFORD if backend=='stabilizer' else
                      _CLIFFORD+' t tdg' if backend in ('clifford_t','clifford_frame','jya_frame') else
                      _SINGLE+' '+_CONTROLLED).split())
        if backend=='factored':alphabet.discard('ccx')
        order={'cyclotomic':16,'cyclotomic32':32,'observer32':32,'cyclotomic64':64,'cyclotomic_pow2':4096}.get(backend,0)
        for bits in range(1,13):
            k=1<<bits
            if k<=order and (backend=='cyclotomic_pow2' or k>=16):
                alphabet.update((f'p{k}',f'p{k}dg',f'cp{k}',f'cp{k}dg'))
        ops=document.get('operations',[])
        names={o[0] for o in ops if isinstance(o,list) and len(o)==2 and isinstance(o[0],str)} if isinstance(ops,list) else set()
        ranges=dict(LIMIT_RANGES)
        if backend=='cyclotomic_pow2':ranges['max_branches']=(1,1_048_576)
        applicable={'max_work','max_coefficient_bits'} | {
            'factored':{'max_bond','max_coefficients'},'observer':{'max_terms'},
            'stabilizer':{'max_generators'},'clifford_t':{'max_terms'},
            'clifford_frame':{'max_generators','max_branches','max_pairs'},
            'jya_frame':{'max_generators','max_branches','max_pairs'},
            'observer32':{'max_terms'},'cyclotomic':{'max_branches'},
            'cyclotomic32':{'max_branches'},'cyclotomic64':{'max_branches'},
            'cyclotomic_pow2':{'max_branches'}}[backend]
        row = dict(backend=backend, requested=backend == requested,
                   unsupported_gates=sorted(names-alphabet),resource_caps={k:ranges[k] for k in sorted(applicable)},
                   input_bytes_cap=MAX_INPUT_BYTES,
                   query_caps=dict(entries=32,scalar_evaluations=4096 if backend=='cyclotomic_pow2' else 256,
                                   distribution_width=12 if backend=='cyclotomic_pow2' else 8))
        try:
            circuit, canonical = validate(probe)
        except (ValueError, TypeError) as error:
            row.update(status='rejected', reason=str(error))
        else:
            row.update(status='accepted', limits=canonical['limits'],
                       gates=len(canonical['operations']), n_qubits=circuit.n_qubits)
        if dropped:
            row['options_dropped_for_probe'] = dropped
        rows.append(row)
    accepted = [r['backend'] for r in rows if r['status'] == 'accepted']
    requested_row = next(r for r in rows if r['requested'])
    return dict(schema=CHECK_SCHEMA, requested_backend=requested,
                requested_status=requested_row['status'],
                requested_reason=requested_row.get('reason'),
                accepted_backends=accepted, backends=rows,
                scope='static validation of width, gate alphabet, query shape and options; '
                      'execution budgets are not predicted',
                capabilities={b: CAPABILITIES[b] for b in BACKENDS})


def capability_table():
    """Markdown table of the static capability record, for the README."""
    header = '| Backend | Width | Gates | Queries | Options | Default limits | Notes |'
    lines = [header, '| --- | --- | --- | --- | --- | --- | --- |']
    for backend in BACKENDS:
        c = CAPABILITIES[backend]
        lines.append(f"| `{backend}` | {c['width']} | {c['gates']} | {c['queries']} | "
                     f"{c['options']} | {c['limits']} | {c['notes']} |")
    return '\n'.join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog='nrqc check', description=__doc__)
    parser.add_argument('input', nargs='?', help='JSON request path, or - for stdin')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--table', action='store_true',
                        help='print the static capability table as Markdown instead of JSON')
    args = parser.parse_args(argv)
    if args.table:
        text = capability_table() + '\n'
        if args.out:
            args.out.write_text(text, encoding='utf-8')
        print(text, end='')
        return 0
    if args.input is None:
        parser.error('an input path is required unless --table is given')
    try:
        if args.input == '-':
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(args.input).open('rb') as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('calculator input exceeds 64 MiB')
        result = check(loads(raw.decode('utf-8')))
    except (ValueError, TypeError, OSError, UnicodeDecodeError) as error:
        result = dict(schema=CHECK_SCHEMA, requested_status='invalid_request', error=str(error),
                      accepted_backends=[], backends=[])
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if args.out:
        args.out.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    if result['requested_status'] == 'invalid_request':
        return 2
    return 0 if result['requested_status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())
