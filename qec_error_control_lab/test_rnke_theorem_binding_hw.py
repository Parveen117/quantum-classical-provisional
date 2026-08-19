import unittest, random
from fractions import Fraction as Fr
from rnke_theorem_binding_hw import ldl_inertia, build, analyse_case

class T(unittest.TestCase):
    def test_inertia_exact_on_known(self):
        self.assertEqual(ldl_inertia([[Fr(0),Fr(1)],[Fr(1),Fr(0)]])[0], (1,0,1))
        self.assertEqual(ldl_inertia([[Fr(2),Fr(0)],[Fr(0),Fr(-3)]])[0], (1,0,1))
        self.assertEqual(ldl_inertia([[Fr(1),Fr(1)],[Fr(1),Fr(1)]])[0], (1,1,0))
    def test_inertia_matches_random_congruence(self):
        rng=random.Random(7)
        for _ in range(20):
            n=5; sig=[rng.choice([1,-1,0]) for _ in range(n)]
            P=[[Fr(rng.randint(-3,3)) for _ in range(n)] for _ in range(n)]
            M=[[sum(P[a][i]*sig[a]*P[a][j] for a in range(n)) for j in range(n)] for i in range(n)]
            # inertia of PᵀΣP equals inertia of Σ restricted if P invertible; check only sign-count bounds
            (p,z,m),_,_=ldl_inertia(M)
            self.assertLessEqual(p, sum(1 for s in sig if s>0)); self.assertLessEqual(m, sum(1 for s in sig if s<0))
    def test_hardware_binding_passes_and_seam_integer_equals_weight(self):
        c=build(); self.assertEqual(c["classification"],"PASS_RNKE_THEOREM_BINDING_HW_V1")
        for case in c["cases"]:
            self.assertEqual(case["T1_seam_integer"]["k_sigma"], case["T1_seam_integer"]["declared_error_weight"])
    def test_renaming_control_residue_inertia_is_generic(self):
        # TAUT-1 renaming test: random ±1 shot data also yields (7,0,1) -> inertia shape is NOT a finding
        rng=random.Random(3); counts={}
        for _ in range(2000):
            b="".join(rng.choice("01") for _ in range(8)); counts[b]=counts.get(b,0)+1
        r=analyse_case({"label":"random","syndrome_counts":counts,"expected_syndrome":"00000000","modal_syndromes":["x"]})
        self.assertEqual(tuple(r["T2_square_residue"]["residue_inertia_D=G-σσᵀ"]), (7,0,1))
    def test_deterministic(self):
        self.assertEqual(build()["certificate_sha256"], build()["certificate_sha256"])
if __name__=="__main__": unittest.main()
