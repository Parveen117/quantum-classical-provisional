"""Building the encoded tree site: fusion cost and storage (v0.27).

TREE_CODE.md priced a logical site in photons and left open what it costs
to build. A tree graph state is a root star with b0 block stars attached; a
star graph state is a GHZ state up to local Hadamards, so every star is
grown exactly as in FUSION_NETWORK.md: from a 3-site GHZ by fusing 3-site
resources at success 1/2 (drift +1/2). Attaching a block to the root star is
one type-I fusion between a spare root leaf and the block centre: success
1/2, and a failure costs that leaf and the whole block. With r spare leaves
the build succeeds exactly when at most r attachments fail (negative
binomial). Every attempt is a storage round, so the photons already built
pay the memory m per round: the survival of the build is an exact
probability generating function in m. Bell pairs per site, build success,
storage survival and the net effect on the v0.25 walk follow. Nothing is
measured; no encoded site exists.
"""
from fractions import Fraction
from math import comb

from .model import ResourceLimit, integer, rational
from .fusion_network import FUSION_SUCCESS, chain_walk
from .loss_tolerant_code import effective_memory, tree
from .chain_memory import memory_walk

BELL_PAIRS_PER_GHZ3 = Fraction(2) / FUSION_SUCCESS   # two Bell pairs, one fusion at 1/2: four expected
GRADES = ("BUILD_DECLARED", "BLOCK_RECORDED", "ATTACHMENT_RECORDED", "BUILD_QUALIFIED")


def _unit(v, label):
    if type(v) is str:
        v = Fraction(v)
    v = rational(v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def star(size, success=FUSION_SUCCESS):
    """A star of `size` photons (centre + size-1 leaves) is a GHZ of `size`
    sites. Grown from one 3-site GHZ by the exact v0.22 walk. Returns the
    reach probability from a fresh GHZ3, expected attempts (each consuming
    one GHZ3), and expected Bell pairs including the first GHZ3."""
    n = integer(size, "size")
    if n < 2:
        raise ValueError("a star has at least two photons")
    if n == 2:
        return dict(size=2, p_reach=Fraction(1), expected_attempts=Fraction(0), expected_bell_pairs=Fraction(1), rounds_pgf=lambda y: Fraction(1))
    if n == 3:
        return dict(size=3, p_reach=Fraction(1), expected_attempts=Fraction(0), expected_bell_pairs=BELL_PAIRS_PER_GHZ3, rounds_pgf=lambda y: Fraction(1))
    w = chain_walk(n, success, 3)
    return dict(size=n, p_reach=w["p_reach_target"], expected_attempts=w["expected_attempts"],
                expected_bell_pairs=BELL_PAIRS_PER_GHZ3 * (1 + w["expected_attempts"]), rounds_pgf=None)


def attachments(blocks, spare, success=FUSION_SUCCESS):
    """b0 blocks must each be attached by a fusion of success s to a spare
    root leaf; the root star carries b0 + spare leaves, so the build succeeds
    exactly when at most `spare` attachments fail: P = sum_{f<=spare}
    C(b0-1+f, f) s^b0 (1-s)^f. Expected attempts and blocks consumed are
    conditional on success; a block is consumed by every attempt."""
    b, r = integer(blocks, "blocks"), integer(spare, "spare")
    s = _unit(success, "success")
    if b < 1 or r < 0 or r > 4096:
        raise ValueError("blocks >= 1, 0 <= spare <= 4096")
    terms = [(f, comb(b - 1 + f, f) * s ** b * (1 - s) ** f) for f in range(r + 1)]
    p = sum(t for _, t in terms)
    e_fail = sum(f * t for f, t in terms) / p
    return dict(blocks=b, spare=r, success=s, p_build=p, expected_failures_given_success=e_fail,
                expected_attempts_given_success=b + e_fail, expected_blocks_consumed=b + e_fail)


def storage_survival(blocks, spare, block_photons, root_photons, memory, success=FUSION_SUCCESS):
    """Exact expectation of the survival of every photon of the finished site
    through the attachment rounds, given the build succeeds. Attachment j
    (j = 1..b0) takes G_j rounds, G_j geometric on {1, 2, ...} with parameter
    s; during those rounds the root star (root_photons, counted whole: a
    lower bound) and the j-1 attached blocks (block_photons each) are stored.
    With y_j = m^(root + (j-1) block), E[y^G] = s y / (1 - (1-s) y). The
    product over j, truncated to at most `spare` failures in total, is
    computed exactly by expanding the failure count."""
    b, r = integer(blocks, "blocks"), integer(spare, "spare")
    m, s = _unit(memory, "memory"), _unit(success, "success")
    bp, rp = integer(block_photons, "block photons"), integer(root_photons, "root photons")
    # distribute f total failures over the b attachments: each attachment j with f_j failures contributes
    # y_j^(1 + f_j) s (1-s)^f_j ; sum over compositions with sum f_j <= r, exact via dynamic programming
    table = {0: Fraction(1)}            # failures so far -> accumulated weight
    for j in range(1, b + 1):
        y = m ** (rp + (j - 1) * bp)
        new = {}
        for f_sofar, wgt in table.items():
            for f in range(r - f_sofar + 1):
                new[f_sofar + f] = new.get(f_sofar + f, Fraction(0)) + wgt * y ** (1 + f) * s * (1 - s) ** f
        table = new
    joint = sum(table.values())                         # E[survival ; build succeeds]
    p_build = attachments(b, r, s)["p_build"]
    return dict(blocks=b, spare=r, memory=m, survival_given_success_lower_bound=joint / p_build, joint=joint, p_build=p_build)


def site_build(branching, spare, memory, success=FUSION_SUCCESS):
    """The whole encoded site: b0 block stars of b1+1 photons, a root star of
    b0+spare+1 photons, b0 attachments. The root photon is measured out at the
    end (TREE_CODE.md); spare leaves not consumed are measured out in Z."""
    b0, b1 = (integer(v, "branching") for v in branching)
    r = integer(spare, "spare")
    parent, _ = tree(branching)
    block = star(b1 + 1, success)
    root = star(b0 + r + 1, success)
    att = attachments(b0, r, success)
    blocks_needed = att["expected_blocks_consumed"]
    bell = blocks_needed * block["expected_bell_pairs"] / block["p_reach"] + root["expected_bell_pairs"] / root["p_reach"]
    surv = storage_survival(b0, r, b1 + 1, b0 + r + 1, memory, success)
    return dict(branching=[b0, b1], photons_in_site=len(parent), spare=r, memory=surv["memory"],
                block=dict(size=b1 + 1, p_reach=block["p_reach"], bell_pairs=block["expected_bell_pairs"]),
                root=dict(size=b0 + r + 1, p_reach=root["p_reach"], bell_pairs=root["expected_bell_pairs"]),
                p_attach_all=att["p_build"], expected_blocks_consumed=blocks_needed,
                expected_bell_pairs_per_site_lower_bound=bell,
                build_storage_survival_lower_bound=surv["survival_given_success_lower_bound"],
                note="star growth rounds are not charged to storage (only attachment rounds): the bound is optimistic there and pessimistic in counting the full root star")


def net_benefit(target_sites, branching, spare, memory):
    """Does the encoded site pay? Compare the v0.25 bare walk with the encoded
    walk (v0.26, lower bound) multiplied by the build survival, per site, and
    report the Bell pairs per logical site."""
    e = effective_memory(branching, memory)
    b = site_build(branching, spare, memory)
    floor = Fraction(int(e["m_eff"] * (1 << 20)), 1 << 20)
    bare = memory_walk(target_sites, memory)["p_reach_target"]
    enc = memory_walk(target_sites, floor)["p_reach_target"]
    per_site_build = b["p_attach_all"] * b["build_storage_survival_lower_bound"]
    n = integer(target_sites, "sites")
    one_shot = per_site_build ** n if n <= 4096 else None
    delivered_cost = b["expected_bell_pairs_per_site_lower_bound"] / per_site_build if per_site_build else None
    return dict(target_sites=n, branching=list(branching), spare=spare, memory=b["memory"], m_eff=e["m_eff"],
                p_reach_bare=bare, p_reach_encoded_lower_bound=enc,
                p_site_built_and_stored=per_site_build,
                one_shot=dict(p_all_sites=one_shot, pays=(enc * one_shot > bare) if one_shot is not None else None,
                              law="every site built once, in series with the register: (p_build survival)^N, a second M1-type cliff"),
                site_multiplexed=dict(bell_pairs_per_delivered_site=delivered_cost,
                                      bell_pairs_for_register=delivered_cost * n if delivered_cost else None,
                                      pays=enc > bare,
                                      law="sites built offline, retried until built and stored, then switched in: cost 1/(p_build survival) per site, the register walk runs at m_eff"))


def build_grade(record):
    """Fail-closed: BUILD_DECLARED -> BLOCK_RECORDED (LAB_RECORDED GHZ witness
    of a block star of the declared size, with the per-site readout rule) ->
    ATTACHMENT_RECORDED (LAB_RECORDED heralded attachment of a block to a root
    leaf with the resulting stabiliser witness) -> BUILD_QUALIFIED (recorded
    attachment success rate and storage survival at or above the declared
    exact values within tolerance)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    blk = record.get("block")
    if not (type(blk) is dict and blk.get("evidence_class") == "LAB_RECORDED" and int(blk.get("size", 0)) >= 3
            and blk.get("ghz_witness") is not None and blk.get("rule") == "exactly one click per site"):
        reasons.append("block needs LAB_RECORDED size >= 3, ghz_witness and the per-site rule")
        return dict(grade="BUILD_DECLARED", reasons=reasons)
    att = record.get("attachment")
    if not (type(att) is dict and att.get("evidence_class") == "LAB_RECORDED" and att.get("heralded") is True
            and att.get("stabiliser_witness") is not None and att.get("success_rate") is not None):
        reasons.append("attachment needs LAB_RECORDED heralded fusion with stabiliser_witness and success_rate")
        return dict(grade="BLOCK_RECORDED", reasons=reasons)
    tol = Fraction(str(att.get("tolerance", "1/10")))
    rate = _unit(att["success_rate"], "success rate")
    surv = att.get("storage_survival")
    declared = att.get("declared_survival")
    if rate < FUSION_SUCCESS * (1 - tol) or surv is None or declared is None or Fraction(str(surv)) < Fraction(str(declared)) * (1 - tol):
        reasons.append("attachment success rate or storage survival below declared beyond tolerance")
        return dict(grade="ATTACHMENT_RECORDED", reasons=reasons)
    return dict(grade="BUILD_QUALIFIED", reasons=reasons)
