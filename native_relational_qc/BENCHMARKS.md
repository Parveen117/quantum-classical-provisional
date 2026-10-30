# Retained same-input comparisons

These are local pipeline timings, not a claim of quantum advantage or a kernel
speed ranking. All six JSON inputs and every timed sample are retained. Every
completed reference answers the identical queries and agrees with the NRQC
decimal displays within 1e-9. NRQC provides exact arithmetic/enclosures; Aer MPS
uses floating point with truncation disabled. Stim handles Clifford inputs only.

## Results

Historical integration measurements retained in `c1bb8e4`, without changing the
numbers after the subsequent arithmetic optimizations. Milliseconds, median
of three fresh-process trials. Conversion, execution,
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

## Full-register 12-bit runtime qualification

The flat backend now accepts an explicit branch cap up to 1,048,576. A regression
executes 131,072 branches and checks the exact probability, exceeding the old
65,536 ceiling. Coefficient and whole-batch work limits remain enforced.

The full-register N=141, base 2, 12-bit arithmetic-oracle workload now completes
inside the unchanged 300-second worker deadline in two fresh-process trials.
Both execute the same 45,132 gates on 40 wires after Panini rewriting, with
`max_branches=1048576`, `max_work=1000000000` and 4096 coefficient bits. The
canonical request hash is identical to the retained original timeout.

| Trial | Worker wall seconds | Calculation seconds | Preparation seconds | Child peak RSS (MiB) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 160.102 | 155.853 | 141.202 | 1196.746 |
| 2 | 190.228 | 168.388 | 148.154 | 1196.688 |

Every one of the 4,096 exact output probabilities agrees with the independent
finite Fourier-sum reference. Both runs produce the same exact distribution
hash, use 195,338,092 logical work units and reach 188,412 branches. No amplitude
is truncated; no factors or order are supplied. The saved full output includes
exact coefficients and decimal enclosures. The replay verifier also rejects
a changed probability and a missing bin.

The improvements are exact signed coefficient rotations for phase gates,
a shared Hadamard product using a four-block integer transform, native-width
magnitude checks, and bounded sparse-pair products for normalization. Overflow
checks retain the Python-integer fallback. Logical product counts and the order
of budget checks are preserved, including failure at each work cutoff.

These are local runtime qualifications on the shared Linux x86_64 host with
Python 3.12.14, NumPy 2.5.4 and one BLAS/OpenMP thread. Trial 2 overlapped the jet
regression audit. `readout_workers` is 1 for this single distribution query;
this measurement does not attribute a speedup to parallel query readout.
Wall time includes worker startup and result transfer; calculation time excludes
those costs, and preparation is a subset of calculation. Child peak RSS includes
serialization. Construction and independent verification are outside the worker
deadline. Performance on other hosts or inputs must be measured separately.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python benchmarks/full_register_12_audit.py --modulus 141 --timeout 300 \
  --out /tmp/full-register-12-trial.json --full-result /tmp/full-register-12-result.json

# Replay the retained exact output, current source hashes and negative controls.
python benchmarks/verify_full_register_12.py \
  --input benchmarks/comparisons/full_register_12_20261031_input.json.gz \
  --result benchmarks/comparisons/full_register_12_20261031_result.json.gz \
  --trials benchmarks/comparisons/full_register_12_optimized_20261031_run1.json \
           benchmarks/comparisons/full_register_12_optimized_20261031_run2.json \
  --out /tmp/full-register-12-qualification.json
```

[Qualification and artifact hashes](../benchmarks/comparisons/full_register_12_qualification_20261031.json),
[trial 1](../benchmarks/comparisons/full_register_12_optimized_20261031_run1.json),
[trial 2](../benchmarks/comparisons/full_register_12_optimized_20261031_run2.json),
[compressed input](../benchmarks/comparisons/full_register_12_20261031_input.json.gz),
[compressed exact output](../benchmarks/comparisons/full_register_12_20261031_result.json.gz).
The [validation summary](../benchmarks/comparisons/FULL_REGISTER_12_VALIDATION.md)
links full-suite logs for all three CI variants and the local run.
The [original timeout](../benchmarks/comparisons/full_register_12.json) is retained
unchanged. The separately documented [record-conditioned path](RECORD_PHASE.md)
is a different execution strategy; its timing is not used here.

Query threads share one prepared state and one work budget; they are opt-in and
are not advertised as a measured speedup. Sparse/dense multiplication selects
integer rotations/convolution or Python-integer products from operand support
and overflow bounds, with independent exact reference tests.
