"""Frozen repeated loss-event campaigns with per-run yield and error gates."""
import argparse
import copy
from fractions import Fraction
import json
from pathlib import Path

from quantum_native_bridge_pro import VerificationError
from .calculator import MAX_INPUT_BYTES, _object, loads
from .compact import ResourceLimit, _integer
from .experiment_campaign import _match_acquisitions
from .loss_acquisition import REJECTS, verify_loss_observation, verify_loss_plan
from .model_experiment import _rational, _seal, _text, _unseal
from .self_learning import FIELD, digest


CAMPAIGN_SCHEMA = "nrqc-loss-campaign-v1"
REPORT_SCHEMA = "nrqc-loss-campaign-report-v1"


def _group(plan):
    experiment = plan["experiment"]
    return digest(dict(prediction=experiment["prediction"]["fingerprint"], binding=experiment["binding"],
                       policy=plan["click_policy"], reference=plan["reference_spec"], thresholds=plan["thresholds"]))


def loss_campaign_plan(plans, *, name, minimum_repetitions):
    _text(name, "loss campaign name")
    minimum = _integer(minimum_repetitions, "minimum repetitions", 1, 64)
    if not isinstance(plans, list) or not 1 <= len(plans) <= 64:
        raise ValueError("a frozen loss campaign requires 1..64 loss experiment plans")
    run_ids, fingerprints, groups = set(), set(), {}
    for plan in plans:
        verify_loss_plan(plan)
        run_id = plan["experiment"]["run_id"]
        if run_id in run_ids or plan["fingerprint"] in fingerprints:
            raise ValueError("loss campaign plans require unique run identities and fingerprints")
        run_ids.add(run_id)
        fingerprints.add(plan["fingerprint"])
        group = _group(plan)
        groups[group] = groups.get(group, 0) + 1
    if any(count < minimum for count in groups.values()):
        raise ValueError("every loss comparison group needs the declared minimum repetitions")
    return _seal(dict(schema=CAMPAIGN_SCHEMA, name=name, minimum_repetitions=minimum,
                      plans=copy.deepcopy(plans), planned_groups=groups,
                      qualification_policy="every planned loss run present and individually qualified; no failures",
                      evidence_class="OFFLINE_LOSS_CAMPAIGN_PLAN", hardware_submissions=0))


def verify_loss_campaign(campaign):
    _unseal(campaign, CAMPAIGN_SCHEMA)
    replay = loss_campaign_plan(campaign["plans"], name=campaign["name"], minimum_repetitions=campaign["minimum_repetitions"])
    if replay != campaign:
        raise ValueError("loss campaign differs from its regenerated fixed plan")
    return dict(status="verified", fingerprint=campaign["fingerprint"])


def loss_campaign_report(campaign, observations, *, failures=None):
    verify_loss_campaign(campaign)
    planned = {plan["fingerprint"]: plan for plan in campaign["plans"]}
    seen, failed = _match_acquisitions(planned, observations, failures, verify=verify_loss_observation,
                                      binding_of=lambda plan: plan["experiment"]["binding"])
    groups, run_results, missing, incomplete, origins = {}, [], [], [], {}
    for fingerprint, plan in planned.items():
        group = _group(plan)
        item = groups.setdefault(group, dict(planned=0, observed=0, failed=0, missing=0,
                                            qualified_runs=0, conditional_incomplete_runs=0,
                                            planned_attempts=0, attempts_observed=0, accepted_observed=0,
                                            accepted_marginal_counts={"0": 0, "1": 0}, rejected_counts=dict.fromkeys(REJECTS, 0),
                                            yields=[], conditional_errors=[]))
        item["planned"] += 1
        item["planned_attempts"] += plan["experiment"]["shots"]
        run_id = plan["experiment"]["run_id"]
        if fingerprint in seen:
            report = seen[fingerprint]
            item["observed"] += 1
            item["attempts_observed"] += report["attempts"]
            item["accepted_observed"] += report["accepted"]
            item["qualified_runs"] += int(report["qualification_passed"])
            if report["status"] == "incomplete":
                item["conditional_incomplete_runs"] += 1
                incomplete.append(fingerprint)
            item["yields"].append(Fraction(report["accepted"], report["attempts"]))
            if report["conditional_absolute_error"] is not None:
                item["conditional_errors"].append(FIELD.from_dict(report["conditional_absolute_error"]))
            for bit in ("0", "1"):
                item["accepted_marginal_counts"][bit] += report["accepted_marginal_counts"][bit]
            for category in REJECTS:
                item["rejected_counts"][category] += report["rejected_counts"][category]
            origin = report["evidence_class"]
            origins[origin] = origins.get(origin, 0) + 1
            run_results.append(dict(run_id=run_id, plan_fingerprint=fingerprint, status="observed",
                                    conditional_status=report["status"], qualification_passed=report["qualification_passed"],
                                    accepted_yield=report["accepted_yield"], observation_fingerprint=report["fingerprint"]))
        elif fingerprint in failed:
            item["failed"] += 1
            run_results.append(dict(run_id=run_id, plan_fingerprint=fingerprint, status="failed", failure=failed[fingerprint]))
        else:
            item["missing"] += 1
            missing.append(fingerprint)
            run_results.append(dict(run_id=run_id, plan_fingerprint=fingerprint, status="missing"))
    for item in groups.values():
        yields, errors = item.pop("yields"), item.pop("conditional_errors")
        maximum = FIELD(0)
        for error in errors:
            if (error - maximum).real_sign() > 0:
                maximum = error
        item["pooled_accepted_yield"] = _rational(Fraction(item["accepted_observed"], item["attempts_observed"])) if item["attempts_observed"] else None
        item["minimum_observed_yield"] = _rational(min(yields)) if yields else None
        item["conditional_results_available"] = len(errors)
        item["mean_conditional_error"] = (sum(errors, FIELD(0)) / len(errors)).to_dict() if errors else None
        item["maximum_conditional_error"] = maximum.to_dict() if errors else None
        accepted = item["accepted_observed"]
        item["pooled_conditional_probability_one"] = _rational(Fraction(item["accepted_marginal_counts"]["1"], accepted)) if accepted else None
        item["qualified"] = item["observed"] == item["planned"] and item["qualified_runs"] == item["planned"]
    complete = not missing
    qualified = complete and not failed and all(item["qualified"] for item in groups.values())
    return _seal(dict(schema=REPORT_SCHEMA, campaign=copy.deepcopy(campaign),
                      observations=[seen[p] for p in planned if p in seen], failures=[failed[p] for p in planned if p in failed],
                      status="complete" if complete else "incomplete", qualification_passed=qualified,
                      planned_runs=len(planned), observed_runs=len(seen), failed_runs=len(failed), missing_plans=missing,
                      conditional_incomplete_plans=incomplete, groups=groups, run_results=run_results, declared_origins=origins,
                      evidence_class="SYNTHETIC_LOSS_CAMPAIGN_QUALIFICATION" if all(
                          plan["experiment"]["binding"]["origin"] == "synthetic" for plan in planned.values()) else "DECLARED_LOSS_CAMPAIGN_QUALIFICATION",
                      source_authentication="not_performed", hardware_submissions=0,
                      scope="complete refers to run-slot accounting; pooled statistics do not replace any per-run qualification gate"))


def verify_loss_campaign_report(report):
    _unseal(report, REPORT_SCHEMA)
    replay = loss_campaign_report(report["campaign"], report["observations"], failures=report["failures"])
    if replay != report:
        raise ValueError("loss campaign report differs from exact replay")
    return dict(status="verified", fingerprint=report["fingerprint"], accounting_status=report["status"],
                qualification_passed=report["qualification_passed"])


def main(argv=None, *, command="loss-campaign-plan"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    if command == "loss-campaign-report":
        parser.add_argument("observations", nargs="*", type=Path)
        parser.add_argument("--ledger", type=Path)
        parser.add_argument("--failures", type=Path)
        parser.add_argument("--require-qualified", action="store_true")
    args = parser.parse_args(argv)
    def read(path):
        with path.open("rb") as stream:
            return loads(stream.read(MAX_INPUT_BYTES + 1).decode("utf-8"))
    try:
        document = read(args.input)
        if command == "loss-campaign-plan":
            _object(document, ("name", "minimum_repetitions", "plans"))
            output = loss_campaign_plan(document["plans"], name=document["name"], minimum_repetitions=document["minimum_repetitions"])
        elif command == "loss-campaign-report":
            if args.ledger and args.observations:
                raise ValueError("choose observation files or one dedicated loss-campaign ledger")
            if args.ledger:
                from .experiment_ledger import read_observations
                observations = read_observations(args.ledger)
            else:
                observations = [read(path) for path in args.observations]
            output = loss_campaign_report(document, observations, failures=read(args.failures) if args.failures else [])
        else:
            output = verify_loss_campaign_report(document)
        code = 3 if command == "loss-campaign-report" and args.require_qualified and not output["qualification_passed"] else 0
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
