# Loss-aware acquisition extension: written contract

Monty · 12 November 2026 · Event intake and conditional-reference contract implemented.

The current [loss acquisition interface](native_relational_qc/LOSS_ACQUISITION.md)
implements frozen detector policies, retained raw events, explicit conditional
references, exact yield/readout gates and replay in the existing ledger.
[Repeated campaigns](native_relational_qc/LOSS_CAMPAIGN.md) preserve all planned
run slots and per-run qualification gates. Measured instrument and detector-response
evidence remain the physical integration stage.

The original classifier intake accounts for unconditional binary shots. A photonic
controller may instead return failed heralds, absent clicks and invalid code
occupations. Its next adapter must retain those events before interpreting an
accepted bit histogram.

## Source boundary

[LOSS_LEDGER.md](phase_seam_foundation/LOSS_LEDGER.md) models retained photon-number
classes and a declared per-site readout rule. Its model distinguishes a missed
herald from a false herald and accounts for rejected events.
[LOSS_BUDGET_810.md](phase_seam_foundation/LOSS_BUDGET_810.md) keeps declared stage
transmissions distinct from measured efficiencies.
[LOSS_REFRESH.md](phase_seam_foundation/LOSS_REFRESH.md) states its ideal-gate and
input-independent heralded-transfer assumptions, and leaves a physical loss-aware
measurement protocol open. [PHOTONIC_IO.md](phase_seam_foundation/PHOTONIC_IO.md)
retains all output detectors, heralds, unexpected outputs and guard events.
Their exact current source hashes are in
[LOSS_AWARE_ACQUISITION_SOURCES.json](LOSS_AWARE_ACQUISITION_SOURCES.json).

## Event accounting

Before acquisition, freeze the attempt budget N, detector/channel map, timing
windows, encoding, acceptance predicate and its precedence for overlapping raw
flags. Declare a mutually exclusive partition of accepted bit outcomes and
rejected categories such as no herald, absent detection, ambiguous detection,
guard/code violation and unclassified event. Retain the original click/flag
artifact and the deterministic policy hash. Unknown events remain visible.

For accepted counts c_b and reject counts r_j, require nonnegative integers and

\[
N=\sum_b c_b+\sum_j r_j,\qquad A=\sum_b c_b.
\]

Report both accepted yield A/N and the joint per-attempt histogram
`accepted:b -> c_b/N`, `rejected:j -> r_j/N`. When A is positive, report the
conditional accepted-bit histogram c_b/A as an additional distribution. When
A is zero, conditional readout is undefined and qualification remains incomplete.
Do not fill it with a zero or uniform distribution.

A no-click event alone does not identify a lost-photon count or prove a genuine
fusion. Latent model/environment labels need a declared observable witness before
they become acquisition fields. Record the detector facts and the policy's
classification separately from that physical interpretation.

## Conditional reference

The existing ideal unitary prediction supplies a binary readout distribution.
A heralded instrument needs its own expected joint outcomes. For a declared
instrument with accepted maps E_(A,b), the reference is

\[
p_{A,b}=\operatorname{Tr} E_{A,b}(\rho),\quad
s=\sum_b p_{A,b},\quad q_b=p_{A,b}/s\quad(s>0).
\]

Equating q_b with the old unitary readout requires a separately established
instrument relation. One sufficient relation is an accepted channel
`E_A(rho) = s U rho U*` with positive input-independent s on the admitted inputs.
The retained loss-refresh source assumes such an ideal successful transfer in
its own model; it does not supply that relation for an arbitrary lab classifier.
An observed acceptance flag by itself does not establish it.

Freeze separate engineering thresholds for accepted yield, minimum accepted
counts and conditional readout error, with the appropriate instrument reference.
Preserve every per-run result. A high conditional agreement with vanishing yield
must not conceal a failed yield requirement. Rejected and unclassified fractions
remain in the campaign summary. No significance claim follows from these fixed
engineering thresholds alone.

## Extension contract

Use a distinct versioned event/result schema, the policy-driven click decoder,
a conditional-instrument reference binding and a campaign extension. Reuse the
existing artifact hashing, calibrated context, readout maps, idempotent ledger
and exact rational comparisons. Retain unsuccessful attempts and explicit retry
plans. Keep the currently qualified unconditional schema unchanged.

Qualification controls must cover count conservation, zero accepted events,
overlapping flags, unclassified clicks, a biased-heralding reference, identical
conditional histograms with different yields, and phase/readout mappings.
Connect the finite model to measured detector response and encoding evidence
before promoting the protocol into an experimental qualification.
