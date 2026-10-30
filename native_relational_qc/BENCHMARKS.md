# Retained same-input comparisons

These are local pipeline timings, not a claim of quantum advantage or a kernel
speed ranking. All six JSON inputs and every timed sample are retained. Every
completed reference answers the identical queries and agrees with the NRQC
decimal displays within 1e-9. NRQC provides exact arithmetic/enclosures; Aer MPS
uses floating point with truncation disabled. Stim handles Clifford inputs only.

## Results

Milliseconds, median of three fresh-process trials. Conversion, execution,
query readout and formatting are included; imports/process startup are excluded
from this column. Raw wall times and process peak RSS are also retained.

| Identical input | NRQC | Aer MPS | Stim |
| --- | ---: | ---: | ---: |
| bell_2 | 10.663 | 21.520 | 0.306 |
| clifford_24 | 47.100 | 417.473 | 2.024 |
| dense_clifford_t_10 | 7662.028 | 51.075 | unsupported |
| dyadic_phase_8 | 300.487 | 37.592 | unsupported |
| ghz_256 | 22.811 | 172.467 | 2.982 |
| ghz_64 | 9.202 | 42.860 | 1.047 |

**Losses are retained:** Aer is substantially faster on the dense Clifford+T
and dyadic-phase examples, and Stim is faster on every supported Clifford case
in this sample. NRQC's pipeline is faster than Aer on these four Clifford cases;
Aer conversion overhead is included, so this does not establish a faster
simulation kernel. Exact arithmetic and floating-point arithmetic have different
cost/accuracy contracts. Six small deterministic workloads do not represent all
circuits. No result is discarded for being slow or unsupported.

Environment: Python 3.12.14, numpy 2.5.4, qiskit 2.6.1, qiskit-aer 0.18.2, stim 1.16.0.
Linux x86_64 shared execution host; one Aer/BLAS thread. Background validation
can affect timings. Reproduce on the intended machine before drawing hardware
or scalability conclusions. Non-Clifford Stim rows are unsupported, not failures
or slow runtimes.

## Reproduce and inspect

```bash
pip install -e '.[benchmark]'
python benchmarks/compare_backends.py --repeats 3
```

- [Inputs](../benchmarks/comparisons/inputs/)
- [All raw samples, answers, input hashes, versions, wall times and RSS](../benchmarks/comparisons/results.json)
- [Harness](../benchmarks/compare_backends.py)
- [First adapter attempt](../benchmarks/comparisons/adapter_initial_results.json): retained for diagnosis. Its Aer 64/256-wire errors came from a 63-wire transpiler target, not an MPS limitation. The corrected harness lowers to a universal gate alphabet without a hardware coupling map; both now run.

## Full-register 12-bit boundary

The flat backend now accepts an explicit branch cap up to 1,048,576. A regression
executes 131,072 branches and checks the exact probability, exceeding the old
65,536 ceiling. Coefficient and whole-batch work limits remain enforced.

The retained full-register N=141, base 2, 12-bit arithmetic-oracle run uses
45,132 gates after Panini rewriting, `max_branches=1048576` and
`max_work=1000000000`. It reached the 300-second wall limit and returned no
partial answer. **This workload is not qualified as completed.** Lifting one
support cap does not remove the cost of a full-register exact distribution.

```bash
python benchmarks/full_register_12_audit.py --modulus 141 --timeout 300 \
  --out benchmarks/comparisons/full_register_12.json
```

[Retained timeout and program metadata](../benchmarks/comparisons/full_register_12.json).
The separately documented [record-conditioned path](RECORD_PHASE.md) is a
different execution strategy; its timing must not be substituted for this run.

Query threads share one prepared state and one work budget; they are opt-in and
are not advertised as a measured speedup. Sparse/dense multiplication selects
integer rotations/convolution or Python-integer products from operand support
and overflow bounds, with independent exact reference tests.
