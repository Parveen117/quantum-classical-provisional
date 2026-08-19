import unittest, math
from adaptive_dd import select_schedule, plan, analyse, _synthetic_counts, fit_decay, build_circuits, self_test, DELAYS_US

class T(unittest.TestCase):
    def test_selector_rules(self):
        self.assertEqual(select_schedule(100, 190, 0.01).seq, "hahn")          # relaxation-limited
        self.assertEqual(select_schedule(100, 120, 0.01).seq, "cpmg")          # moderate
        self.assertEqual(select_schedule(100, 30, 0.01).seq, "xy4")            # large dephasing
        self.assertIn("DEFERRED", select_schedule(100, 250, 0.01).reason)      # non-Markovian flag
        self.assertEqual(select_schedule(100, 120, 0.01, confidence=0.3).seq, "xy4")  # low conf -> robust
    def test_plan_deterministic_and_has_controls(self):
        cal={"qubits":{"0":{"T1_us":100,"T2_us":80,"readout_error":0.02}}}
        a=plan(cal); b=plan(cal); self.assertEqual(a["plan_sha256"], b["plan_sha256"])
        labels=[x[0] for x in a["qubits"]["0"]["arms"]]
        for need in ("ramsey","hahn","adaptive","random_ctrl","cpmg_4","xy4_2"): self.assertIn(need, labels)
    def test_fit_recovers_T(self):
        T=120.0; taus=DELAYS_US; p=[0.5+0.5*math.exp(-(t/T)**1.2) for t in taus]
        f=fit_decay(taus,p); self.assertLess(abs(f["T_us"]-T)/T, 0.2)
    def test_circuits_shape(self):
        try:
            import qiskit  # noqa: F401
        except ImportError:
            self.skipTest("qiskit not installed; circuit construction is exercised separately")
        cal={"qubits":{"0":{"T1_us":100,"T2_us":40,"readout_error":0.02}}}
        arms=plan(cal)["qubits"]["0"]["arms"]
        cs=build_circuits(0, arms); self.assertEqual(len(cs), len(arms)*len(DELAYS_US))
    def test_synthetic_gives_no_adaptive_effect_by_default(self):
        c=self_test(); self.assertEqual(c["checks"]["headline"], "NO_ADAPTIVE_EFFECT_DD_EXTENSION_ONLY")
    def test_planted_adaptive_effect_detected(self):
        cal={"qubits":{str(i):{"T1_us":150,"T2_us":40,"readout_error":0.02} for i in range(3)}}
        p=plan(cal); counts=_synthetic_counts(p)
        # plant: adaptive arm decays much slower than anything fixed
        for q in counts:
            for t in p["delays_us"]:
                p0=0.5+0.5*math.exp(-(t/5000)**1.2); counts[q]["adaptive"][str(t)]={"0":int(2000*p0),"1":2000-int(2000*p0)}
        c=analyse(p,counts); self.assertEqual(c["checks"]["headline"], "ADAPTIVE_SELECTION_EFFECT")
if __name__=="__main__": unittest.main()
