"""Frozen repeated-acquisition campaigns with explicit missing and failed runs."""
import argparse
import copy
from fractions import Fraction
import json
from pathlib import Path

from quantum_native_bridge_pro import VerificationError

from .calculator import MAX_INPUT_BYTES, _object, loads
from .compact import ResourceLimit, _integer
from .model_experiment import (
    _rational, _seal, _sha, _text, _unseal, verify_observation, verify_plan,
)
from .self_learning import FIELD, digest


CAMPAIGN_SCHEMA = "nrqc-experiment-campaign-v1"
REPORT_SCHEMA = "nrqc-experiment-campaign-report-v1"


def _group(plan):
    # Only identically predicted and measured contexts can share a marginal.
    return digest(dict(prediction=plan["prediction"]["fingerprint"], binding=plan["binding"],
                       measure_wires=plan["measure_wires"], tolerance=plan["tolerance"]))


def campaign_plan(plans, *, name, minimum_repetitions):
    _text(name, "campaign name")
    minimum = _integer(minimum_repetitions, "minimum repetitions", 1, 64)
    if not isinstance(plans, list) or not 1 <= len(plans) <= 64:
        raise ValueError("a frozen campaign requires 1..64 experiment plans")
    run_ids, fingerprints, groups = set(), set(), {}
    for plan in plans:
        verify_plan(plan)
        if plan["run_id"] in run_ids or plan["fingerprint"] in fingerprints:
            raise ValueError("campaign plans require unique run identities and fingerprints")
        run_ids.add(plan["run_id"])
        fingerprints.add(plan["fingerprint"])
        group = _group(plan)
        groups[group] = groups.get(group, 0) + 1
    if any(count < minimum for count in groups.values()):
        raise ValueError("every comparison group must contain the declared minimum repetitions")
    return _seal(dict(schema=CAMPAIGN_SCHEMA, name=name, minimum_repetitions=minimum,
                      plans=copy.deepcopy(plans), planned_groups=groups,
                      qualification_policy="all planned runs present, no failures, every exact error within its frozen tolerance",
                      evidence_class="OFFLINE_CAMPAIGN_PLAN", hardware_submissions=0))


def verify_campaign(campaign):
    _unseal(campaign, CAMPAIGN_SCHEMA)
    replay = campaign_plan(campaign["plans"], name=campaign["name"],
                           minimum_repetitions=campaign["minimum_repetitions"])
    if replay != campaign:
        raise ValueError("campaign differs from its regenerated fixed plan")
    return dict(status="verified", fingerprint=campaign["fingerprint"])


def _failures(failures, planned):
    if not isinstance(failures, list) or len(failures) > len(planned):
        raise ValueError("campaign failures require a bounded list")
    result = {}
    for failure in failures:
        _object(failure, ("plan_fingerprint", "kind", "detail", "job_id", "source_sha256"))
        fingerprint = failure["plan_fingerprint"]
        if fingerprint not in planned or fingerprint in result:
            raise ValueError("failure refers to an unknown or duplicate campaign plan")
        if failure["kind"] not in ("acquisition_failed", "timeout", "cancelled", "not_submitted"):
            raise ValueError("unknown declared acquisition failure kind")
        _text(failure["detail"], "failure detail", 500)
        if failure["job_id"] is not None:
            _text(failure["job_id"], "failed acquisition job identity")
        if failure["source_sha256"] is not None:
            _sha(failure["source_sha256"], "failure source hash")
        result[fingerprint] = copy.deepcopy(failure)
    return result


def _match_acquisitions(planned, observations, failures, *, verify, binding_of):
    """Shared run-slot and acquisition-identity rules for both event protocols."""
    if not isinstance(observations, list) or len(observations) > len(planned):
        raise ValueError("observations require a bounded campaign list")
    seen, jobs = {}, set()
    for report in observations:
        verify(report)
        fingerprint = report["plan"]["fingerprint"]
        if fingerprint not in planned or fingerprint in seen:
            raise ValueError("observation refers to an unknown or duplicate campaign plan")
        if report["plan"] != planned[fingerprint]:
            raise ValueError("observation plan differs from frozen campaign")
        acquisition = report["acquisition"]
        job = tuple(acquisition[k] for k in ("provider", "backend", "job_id"))
        if job in jobs:
            raise ValueError("campaign reuses an acquisition identity")
        jobs.add(job)
        seen[fingerprint] = copy.deepcopy(report)
    failed = _failures([] if failures is None else failures, planned)
    if set(failed) & set(seen):
        raise ValueError("a planned acquisition cannot have both an observation and a failure")
    for fingerprint, failure in failed.items():
        if failure["job_id"] is not None:
            binding = binding_of(planned[fingerprint])
            job = binding["provider"], binding["backend"], failure["job_id"]
            if job in jobs:
                raise ValueError("campaign reuses a successful or failed acquisition identity")
            jobs.add(job)
    return seen, failed


def campaign_report(campaign, observations, *, failures=None):
    """Keep failures/outliers visible; pool only within identical fixed contexts."""
    verify_campaign(campaign)
    planned = {plan["fingerprint"]: plan for plan in campaign["plans"]}
    seen, failed = _match_acquisitions(planned, observations, failures,
                                      verify=verify_observation, binding_of=lambda plan: plan["binding"])
    groups, run_results, missing, origins = {}, [], [], {}
    for fingerprint, plan in planned.items():
        group = _group(plan)
        item = groups.setdefault(group, dict(planned=0, observed=0, failed=0, missing=0,
                                            exact_classifications={}, pooled_marginal_counts={"0": 0, "1": 0},
                                            errors=[], probabilities=[]))
        item["planned"] += 1
        if fingerprint in seen:
            report = seen[fingerprint]
            classification = report["classification"]
            item["observed"] += 1
            counts = item["exact_classifications"]
            counts[classification] = counts.get(classification, 0) + 1
            for bit in ("0", "1"):
                item["pooled_marginal_counts"][bit] += report["marginal_counts"][bit]
            item["errors"].append(FIELD.from_dict(report["absolute_error"]))
            probability = report["observed_probability_one"]
            item["probabilities"].append(Fraction(probability["numerator"], probability["denominator"]))
            origin = report["evidence_class"]
            origins[origin] = origins.get(origin, 0) + 1
            run_results.append(dict(run_id=plan["run_id"], plan_fingerprint=fingerprint,
                                    status="observed", classification=classification,
                                    observation_fingerprint=report["fingerprint"]))
        elif fingerprint in failed:
            item["failed"] += 1
            run_results.append(dict(run_id=plan["run_id"], plan_fingerprint=fingerprint,
                                    status="failed", failure=failed[fingerprint]))
        else:
            item["missing"] += 1
            missing.append(fingerprint)
            run_results.append(dict(run_id=plan["run_id"], plan_fingerprint=fingerprint, status="missing"))
    for item in groups.values():
        errors, probabilities = item.pop("errors"), item.pop("probabilities")
        maximum = FIELD(0)
        for error in errors:
            if (error - maximum).real_sign() > 0:
                maximum = error
        counts = item["pooled_marginal_counts"]
        total = sum(counts.values())
        item["pooled_probability_one"] = _rational(Fraction(counts["1"], total)) if total else None
        item["mean_run_absolute_error"] = (sum(errors, FIELD(0)) / len(errors)).to_dict() if errors else None
        item["maximum_run_absolute_error"] = maximum.to_dict() if errors else None
        item["observed_probability_range"] = [_rational(min(probabilities)), _rational(max(probabilities))] if probabilities else None
        item["qualified"] = (item["observed"] == item["planned"] and
                             item["exact_classifications"] == {"RECOGNITION": item["planned"]})
    complete = not missing
    qualified = complete and not failed and all(item["qualified"] for item in groups.values())
    return _seal(dict(schema=REPORT_SCHEMA, campaign=copy.deepcopy(campaign),
                      observations=[seen[p] for p in planned if p in seen],
                      failures=[failed[p] for p in planned if p in failed],
                      status="complete" if complete else "incomplete", qualification_passed=qualified,
                      planned_runs=len(planned), observed_runs=len(seen), failed_runs=len(failed),
                      missing_plans=missing, groups=groups, run_results=run_results, declared_origins=origins,
                      evidence_class="SYNTHETIC_CAMPAIGN_QUALIFICATION" if all(
                          plan["binding"]["origin"] == "synthetic" for plan in planned.values()) else "DECLARED_CAMPAIGN_QUALIFICATION",
                      source_authentication="not_performed", hardware_submissions=0,
                      scope="fixed per-run engineering tolerances; no pooling across distinct prediction/calibration contexts; no significance claim"))


def verify_campaign_report(report):
    _unseal(report, REPORT_SCHEMA)
    replay = campaign_report(report["campaign"], report["observations"], failures=report["failures"])
    if report != replay:
        raise ValueError("campaign report differs from exact replay")
    return dict(status="verified", fingerprint=report["fingerprint"],
                campaign_status=report["status"], qualification_passed=report["qualification_passed"])


def main(argv=None, *, command="campaign-plan"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    if command == "campaign-report":
        parser.add_argument("observations", type=Path, nargs="*")
        parser.add_argument("--ledger", type=Path)
        parser.add_argument("--failures", type=Path)
        parser.add_argument("--require-qualified", action="store_true",
                            help="exit 3 when a valid report is incomplete or fails its fixed policy")
    args = parser.parse_args(argv)
    def read(path):
        with path.open("rb") as stream:
            return loads(stream.read(MAX_INPUT_BYTES + 1).decode("utf-8"))
    try:
        document = read(args.input)
        if command == "campaign-plan":
            _object(document, ("name", "minimum_repetitions", "plans"))
            output = campaign_plan(document["plans"], name=document["name"],
                                   minimum_repetitions=document["minimum_repetitions"])
        elif command == "campaign-report":
            if args.ledger and args.observations:
                raise ValueError("choose observation files or one dedicated campaign ledger")
            if args.ledger:
                from .experiment_ledger import read_observations
                observations = read_observations(args.ledger)
            else:
                observations = [read(path) for path in args.observations]
            output = campaign_report(document, observations,
                                     failures=read(args.failures) if args.failures else [])
        else:
            output = verify_campaign_report(document)
        code = 3 if command == "campaign-report" and args.require_qualified and not output["qualification_passed"] else 0
    except (ValueError, TypeError, KeyError, OSError, VerificationError) as error:
        output, code = dict(status="invalid_request", error=str(error)), 2
    except ResourceLimit as error:
        output, code = dict(status="incomplete", error=str(error)), 1
    except ArithmeticError as error:
        output, code = dict(status="verification_failed", error=str(error)), 1
    rendered = json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code
