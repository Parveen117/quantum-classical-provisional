# Record-conditioned exact phase estimation (`record_phase`)

The full-register Shor program carries m control wires, turns them all by an
inverse quantum Fourier transform and reads them at the end. This module runs
the same order-finding problem with **one control wire read m times**. Each
reading is written to a classical record, the next phase correction is built
from that record alone, and the wire is reused. The engine follows both
outcomes of every reading, so it returns the exact distribution over complete
records rather than samples. The construction is the semiclassical Fourier
transform of Griffiths and Niu (Phys. Rev. Lett. 76, 3228, 1996), the form in
which Shor's algorithm has been run on recycled qubits (Martín-López et al.,
Nature Photonics 6, 773, 2012; Monz et al., Science 351, 1068, 2016). What is
new here is that the native engine states the equivalence as an exact identity
of branch states, checks it instance by instance against the independent
Fourier law and against the full-register calculator, and uses it to reach
twelve phase bits for N = 141, 143 and 187 within the existing branch cap.

## Protocol

Fix an odd modulus N < 256, a base a coprime to N, a record length
1 <= m <= 12 and the field Q(zeta_M), M = max(8, 2^m). The work register holds
the integer 1. Readings are numbered t = 0, ..., m-1 and reading t uses the
power j_t = m-1-t.

For each t:
1. Prepare the control wire in |+>.
2. Apply the controlled multiplier |v> -> |a^(2^j_t) v mod N> on the work
   register. This is the same reversible arithmetic circuit
   (`modular_arithmetic.append_multiplier`, X/CX/CCX only, clean workspace
   restored) that the full-register program lowers; no multiplication is done
   in Python.
3. Apply the correction R_t = diag(1, zeta_M^(e_t)) to the control, where

       e_t = -(M / 2^m) * sum_{s<t} y_s 2^(s + j_t) = -M * sum_{s<t} y_s 2^(s-t-1),

   an integer determined by the readings y_0, ..., y_(t-1) already taken.
4. Apply a Hadamard to the control and read it in the Z basis. The reading is
   bit t of the record y = sum_t y_t 2^t.

The engine keeps, for every record prefix, the unnormalized work-register
state psi; after a reading with outcome b it becomes
psi_b = (psi + (-1)^b zeta_M^(e_t) U_t psi) / 2, where U_t is the controlled
multiplier's permutation of labels. Its squared norm is the probability of the
prefix. A prefix whose state vanishes exactly is pruned and all its
completions are recorded as zero. At a leaf the probability is
sum_v |psi_y(v)|^2, one exact field product per work label.

## Theorem R1 (exact transfer of the register into the record)

Let A(y, v) = 2^(-m) sum_{x < 2^m, f(x) = v} zeta_(2^m)^(-x y) be the amplitude
of |y>|v> after the full-register program (m Hadamards, controlled
multipliers, inverse QFT), with f(x) = a^x mod N. Then for every record y and
every work label v the unnormalized record branch state satisfies

    psi_y(v) = A(y, v).

In particular the record law P(y) = sum_v |psi_y(v)|^2 equals the readout law
of the full register, the post-measurement work states coincide, and every
decoder (continued fractions with or without doubled denominators) has the
same exact success probability on both.

*Proof.* The m rounds are linear maps on the work register that commute with
one another, since all U_t are powers of the single permutation v -> a v. The
leaf state is therefore the product

    psi_y = prod_t (1 + (-1)^(y_t) zeta_M^(e_t) U_t) / 2 |1>
          = 2^(-m) sum_{S} prod_{t in S} (-1)^(y_t) zeta_M^(e_t) U^(sum_{t in S} 2^(j_t)) |1>,

summed over subsets S of the readings. The map S -> x = sum_{t in S} 2^(j_t)
is a bijection onto [0, 2^m), with t in S exactly when bit j_t of x is set,
and U^x |1> = |f(x)>. So psi_y(v) = 2^(-m) sum_{f(x)=v} c(x, y) with
c(x, y) = prod_{t: x_(j_t)=1} (-1)^(y_t) zeta_M^(e_t). On the other side,
x y / 2^m = sum_{t,s} x_(j_t) y_s 2^(s-t-1), because j_t + s - m = s - t - 1.
Terms with s > t are integers and drop out of zeta_(2^m)^(-xy); the term s = t
gives (-1)^(y_t); the terms s < t give exp(-2 pi i sum_{s<t} y_s 2^(s-t-1)) =
zeta_M^(e_t). Hence c(x, y) = zeta_(2^m)^(-xy) and psi_y(v) = A(y, v). QED

Three remarks follow from the proof rather than from the simulation.

- **R2 (causality of the correction).** Readings later than t enter
  zeta_(2^m)^(-xy) only through integer multiples of 2 pi. That is why the
  register can be cut after every reading: nothing that is still to be read
  is needed to correct the present one.
- **R3 (wires).** The record program uses 1 + width + workspace wires (29 for
  every N < 256) for any m, against m + width + workspace + 1 for the full
  register. The m bits live in the classical record.
- **R4 (what both observers read).** By the proof, P(y) depends on f only
  through the coincidence profile pairs(d) = #{(u, u') : f(u) = f(u'),
  u' - u = d mod 2^m}, as `shor.exact_phase_law` computes it. The register
  read at once and the wire read m times with retained corrections are two
  observers of the same relation; neither sees more than the other.

The identity has the shape that the layer-cut work in the Publications
repository asks for: a cut with its correction supplied in advance from
retained readings, and nothing lost across it. This is a remark on form, not a
claim that the two settings are the same mathematics.

## What the engine checks

- Each round's circuit is executed by the flat backend from the branch's own
  labels with the control wire set; the result must be a single label with the
  amplitude unchanged, the control still set and the workspace clean. The
  label map of a round is computed once per label and reused on every branch
  of that round, since a permutation of labels does not depend on amplitudes.
- The sum of all record probabilities must equal 1 exactly.
- `assess_record` compares every record probability with the independent
  Fourier law and raises on any disagreement before decoding.
- The audit additionally runs the full-register circuit where it fits the
  65,536-branch cap and checks the two distributions for exact equality.
- All budgets (`max_work`, `max_coefficient_bits`, `max_branches` on each
  branch state) cover the whole tree; a failure discards everything.

Run `python -m native_relational_qc.record_phase --modulus 141 --precision 10 --out report.json`.
The general evaluator for mid-circuit measurement, reset and feedback on
Pauli duals over Q(sqrt(2), i) remains [DYNAMIC.md](DYNAMIC.md); this module
is specific to phase estimation on the flat field.

## Measured on this machine

Run `PYTHONPATH=. python benchmarks/record_phase_audit.py`. All rows use base
2 and the arithmetic multiplier circuits. "record s" is the whole record tree
including every multiplier execution and the leaf readout; "full s" is the
full-register flat calculator batch for the same instance, run where it fits
the 65,536-branch cap. Results are in
[record_phase_audit.json](record_phase_audit.json).

| N | bits | wires record / full | record s | full s | support record / full | record = full | success, CF+doubles | success, CF only |
| ---: | ---: | --- | ---: | ---: | --- | --- | ---: | ---: |
| 141 | 8 | 29 / 36 | 11.6 | 7.9 | 46 / 11,724 | exact | 31.5572172% | 4.3549653% |
| 143 | 8 | 29 / 36 | 10.2 | 7.7 | 60 / 14,832 | exact | 6.4962126% | 0 |
| 187 | 8 | 29 / 36 | 7.4 | 6.8 | 40 / 10,048 | exact | 11.6736362% | 0 |
| 141 | 10 | 29 / 38 | 28.5 | 43.8 | 46 / 47,036 | exact | 67.6593021% | 23.8002623% |
| 143 | 10 | 29 / 38 | 29.7 | 40.5 | 60 / 61,424 | exact | 24.9773482% | 12.8593492% |
| 187 | 10 | 29 / 38 | 18.7 | 24.9 | 40 / 40,768 | exact | 43.0547653% | 24.5117931% |
| 141 | 12 | 29 / 40 | 448.9 | over cap | 46 / 188,416 | law only | 90.5345333% | 43.6963776% |
| 143 | 12 | 29 / 40 | 542.3 | over cap | 60 / 245,760 | law only | 36.8736373% | 23.9574965% |
| 187 | 12 | 29 / 40 | 377.1 | over cap | 40 / 163,840 | law only | 56.7589921% | 37.1144568% |

Every record probability in every row equals the independent Fourier law
exactly, and in the six rows where the full register was run the two
distributions are identical element by element (Theorem R1 witnessed). The
twelve-bit rows hold at most 60 amplitudes at a time instead of the 163,840
to 245,760 branches the full register would need; peak process RSS for the
whole audit was 191 MiB. The time of the twelve-bit rows is almost entirely
the leaf readout: 4096 records times the orbit size, one exact 2048-slot
product each.

## Limits

- Ideal operations, perfect reset of the control wire and no noise. Nothing
  here is hardware evidence or a sample.
- The leaf readout costs one exact product per work label per record, the
  same as the full register's readout; the saving is memory
  (O(m * orbit) amplitudes) and wires, not products.
- Decoders, modulus range (< 256) and record length (<= 12) are those of the
  Shor builder; no scaling claim is made.
