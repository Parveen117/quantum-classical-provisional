# Dual-rail route for room-temperature operation — v0.18

**Author: Monty.** Decision of 26 October 2026: develop the technology so that
the device runs at room temperature. This note fixes the route and proves,
in the calculator's exact field, the three statements the route rests on.
No 810 nm core exists yet, no visibility has been measured, and loss is not
modelled; the temperature verdict of v0.17 still grades only recorded logs.

[Code](dual_rail.py) · [Tests](../tests/test_phase_seam_dual_rail.py) ·
[Audit](../benchmarks/dual_rail_audit.py) · [Qualification](dual_rail/qualification.json) ·
[Plan for 2056 sites](dual_rail/plan_2056.json).

## 1. The route

| Choice | v0.9 to v0.17 | v0.18 |
| --- | --- | --- |
| Encoding | one photon over 2^N paths | one photon per site, two rails: 2N modes |
| Single-site gate | exchange MZI on one pair of paths | the same four-heater unit, one per site |
| Two-site primitive | none | type-I fusion on one balanced coupler, heralded, success 1/2 |
| Signal, detector | 1550 nm, SNSPD (cryogenic) | 810 nm, silicon single-photon diodes (room band) |
| Scaling | not scalable (REGISTER_FAMILY.md) | linear counts: 2N modes, 4N heaters, N photons per shot |

The family of REGISTER_FAMILY.md now applies to the carrier as well as to the
verification layer. The price is a probabilistic entangling step that needs
photon-photon interference, so the Hong-Ou-Mandel visibility becomes the
central measured number of the programme.

## 2. Exact boson engine

`fock_amplitude(U, n_in, n_out) = perm(U[out, in]) / sqrt(prod n_in! prod n_out!)`
for at most four photons in at most ten modes, at most two per mode, with
every entry in Q(zeta_64). `evolve` propagates a Fock superposition exactly
and `total_probability` checks unitarity. Permanents of 4x4 blocks are
evaluated by enumeration; this is a few-photon tool, not a boson sampler.

## 3. Theorem D1 (single-site universality from the existing unit)

For every grid angle theta and trims b, a,

`word(pi - theta, 0, b, a) = diag(1, z^{a+16}) * H diag(1, e^{-i theta}) H * diag(1, z^{b+16})`,

with `z = zeta_64`. The middle factor is `e^{-i theta/2} R_x(theta)` and each
diagonal factor is a Z rotation up to global phase, so the four heaters give
a Z-X-Z Euler decomposition: every single-site unitary at continuous angles.
Checked exactly at all 65 sampled angles and twenty trim pairs.

Hong-Ou-Mandel on the same unit, now from the boson engine rather than the
permanent formula of v0.17: coincidence `cos^2 theta`, bunching `sin^2 theta`,
zero coincidence at quadrature.

## 4. Theorem D2 (type-I fusion merges two Bell pairs into GHZ, exactly)

Sites A' A B B' on eight modes, `|Phi+>_{A'A} (x) |Phi+>_{BB'}`, four photons.
Rails a1 and b0 meet on one balanced coupler and are detected. Exactly one
click on that pair happens with probability 1/2 (1/4 per detector); zero or
two clicks happen with probability 1/2 and are failures. On success the
surviving photon on (a0, b1) is a dual-rail site C and the register (A', C,
B') is `(|000> + z^k |111>)/sqrt2` with `k = 48` for one detector and `k =
16` for the other: a GHZ state up to a known Z phase of -pi/2 or +pi/2. After
feeding that phase forward, `<XXX> = 1` exactly for both clicks.

This is the Browne-Rudolph type-I fusion written in path encoding; the
contribution here is the exact evaluation inside the calculator's field, so
the heralded phases and the success fraction are certificates, not fits.

## 5. Negative control and the visibility law

If the photon from A and the photon from B are in orthogonal internal
modes (fully distinguishable), the same circuit still succeeds with
probability 1/2, but the merged register's (000) and (111) components never
share a species in C, so the corrected `<XXX>` is exactly 0. With a convex
mixture of weight V indistinguishable and 1-V distinguishable, the success
probability stays 1/2 and

`<XXX>_corrected = V`

exactly, for every rational V in [0, 1]. V is the HOM visibility the
temperature sweep already records at each point. So the sweep's HOM number
is the fusion fidelity driver: a drop in V with temperature is a drop in
entangling fidelity, and the verdict should treat it as such when the fusion
stage is added to the record.

## 6. Plan and boundary

`room_temperature_plan(N)` declares, for N sites: 2N modes, 4N single-site
heaters, N photons per shot, one coupler per fusion step, 810 nm signal from
a 405 nm pumped degenerate SPDC source, silicon detectors, measurement order
(bright-light calibration, heralded g2(0), HOM visibility, single-site
protocol, fusion of two heralded pairs with `<XXX>` against V, then the
temperature sweep of all of it), and four boundary statements: loss and
multipair emission are not modelled, fusion is heralded and a computer needs
a fusion network or multiplexing, no 810 nm core exists, the verdict grades
only recorded logs.

## 7. Reproduction

```bash
python benchmarks/dual_rail_audit.py
```

Closed: exact few-photon engine, D1 Euler identity, HOM from the engine, D2
fusion with heralded phases, the distinguishable control and the visibility
law, and the declared room-temperature plan for any N.

Open: the 810 nm source and core design, fabrication, loss and detector
budgets, multiplexing or a fusion network, and every measured number.
