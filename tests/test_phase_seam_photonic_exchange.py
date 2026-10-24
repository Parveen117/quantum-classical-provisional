"""Optical routing/transfer identities, native matching and honest shot accounting."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import unittest

from native_relational_qc.phase_backend import Phase64Circuit, prepare
from native_relational_qc.cyclotomic64 import Cyclotomic64 as C, ZETA
from phase_seam_foundation.model import Config, Operation as O, ResourceLimit
from phase_seam_foundation.sector_control import compile_sector_control
from phase_seam_foundation.photonic_exchange import design_photonic_exchange, verify_photonic_exchange, observed_rates


class PhotonicMappingTests(unittest.TestCase):
    def test_all_grid4_encodings_match_native_exchange_for_every_pointer(self):
        for q,a in product(range(4),repeat=2):
            layout=design_photonic_exchange(pair_sum=q,reference=a)
            native=compile_sector_control((O("pair_reset",(0,2,a)),),config=Config(grid=4))
            c=native.controller
            for path in range(16):
                j,b,m=layout.decode(path)
                self.assertEqual(layout.encode(j,b,m),path)
                self.assertEqual((j+b)%4,q)
                source=c.pack((j,0,b,0))|(m << c.records[0].wires[0])
                phases,records=c.unpack(native.image(0,source))
                self.assertEqual(layout.encode(phases[0],phases[2],records[0]),layout.partner(path))
                self.assertEqual(layout.partner(layout.partner(path)),path)

    def test_all_supported_layouts_partition_paths_without_guard_coupling(self):
        for grid in (4,8,16,32,64):
            layout=design_photonic_exchange(grid=grid,pair_sum=grid-1,reference=3)
            ports=tuple(x for pair in layout.pairs for x in pair)+layout.fixed
            self.assertEqual(sorted(ports),list(range(grid**2)))
            self.assertEqual(len(set(ports)),grid**2)
            self.assertNotIn(layout.guard,ports)
            self.assertEqual(len(layout.pairs),grid*(grid-1)//2)
            for p,q in layout.pairs:self.assertEqual(layout.partner(p),q)
            for p in layout.fixed:self.assertEqual(layout.partner(p),p)
            self.assertTrue(verify_photonic_exchange(layout))

    def test_fresh_record_endpoint_reset_keeps_all_old_labels(self):
        for grid in (4,8,64):
            layout=design_photonic_exchange(grid=grid,pair_sum=1,reference=3)
            outputs=[]
            for old in range(grid):
                p=layout.encode(old,(1-old)%grid,0)
                q,coefficient=layout.column(p,32)[0]
                self.assertEqual(coefficient,C(1))
                self.assertEqual(layout.decode(q),(3,(1-3)%grid,(old-3)%grid))
                outputs.append(q)
            self.assertEqual(len(set(outputs)),grid)

    def test_guard_has_no_native_coordinate_or_data_conservation_claim(self):
        layout=design_photonic_exchange()
        for step in (0,1,16,32,63):self.assertEqual(layout.column(layout.guard,step),((layout.guard,C(1)),))
        with self.assertRaises(ValueError):layout.decode(layout.guard)
        with self.assertRaises(ValueError):layout.encode(1,0,0)
        self.assertIn("no independent native closure",layout.netlist()["guard_contract"])


class PhotonicTransferTests(unittest.TestCase):
    def test_mach_zehnder_matrix_matches_existing_exact_phase_engine(self):
        layout=design_photonic_exchange();p,q=layout.pairs[0]
        for steps,input_bit in product(range(64),(0,1)):
            c=Phase64Circuit(1)
            if input_bit:c.add("x",0)
            c.add("h",0)
            for _ in range(steps):c.add("p64dg",0)
            c.add("h",0)
            actual={(p,q)[bit]:v for bit,v in prepare(c).amplitudes.items()}
            self.assertEqual(actual,dict(layout.column((p,q)[input_bit],steps)))

    def test_native_fractional_circuit_matches_all_optical_columns(self):
        layout=design_photonic_exchange(pair_sum=1,reference=2)
        p=compile_sector_control((O("pair_reset",(0,2,2)),),config=Config(grid=4));c=p.controller
        for step in (8,16,32):
            gates=p.verification_circuit((step,)).operations
            for path in range(16):
                j,b,m=layout.decode(path);label=c.pack((j,0,b,0))|(m << c.records[0].wires[0])
                circuit=Phase64Circuit(p.n_qubits+2)
                for bit in range(p.n_qubits):
                    if (label>>bit)&1:circuit.add("x",bit)
                for name,qs in gates:circuit.add(name,*qs)
                actual={}
                for label,amplitude in prepare(circuit).amplitudes.items():
                    self.assertEqual(label>>p.n_qubits,0)
                    phases,records=c.unpack(label)
                    actual[layout.encode(phases[0],phases[2],records[0])]=amplitude
                self.assertEqual(actual,dict(layout.column(path,step)))

    def test_fixed_path_reference_detects_wrong_common_phase_and_dephasing(self):
        layout=design_photonic_exchange()
        plan=layout.experiment_plan();sample=next(s for s in plan["settings"] if s["id"]=="phase_0_0")
        expected=C.from_dict(sample["ideal_plus_probability"])
        self.assertEqual(expected,C(1))
        # i*SWAP has the same endpoint populations as SWAP, but the wrong
        # relative phase against a bypass. Full pointer dephasing also fails.
        wrong_phase=(1+ZETA**16).norm2()/4
        self.assertEqual(wrong_phase,C(F(1,2)))
        self.assertNotEqual(wrong_phase,expected)
        dephased_probability=C(F(1,2))
        self.assertNotEqual(dephased_probability,expected)

    def test_netlist_and_protocol_ideal_probabilities_are_normalized_not_measured(self):
        layout=design_photonic_exchange();net=layout.netlist();plan=layout.experiment_plan()
        self.assertEqual(len(net["exchange_blocks"]),6)
        self.assertEqual(net["bypass_ports"],[0,5,10,15])
        self.assertEqual(net["guard_ports"],[16])
        self.assertIsNone(net["measurements"]);self.assertEqual(net["status"],"DESIGN_ONLY")
        self.assertEqual(plan["status"],"NOT_RUN");self.assertEqual(plan["settings_count"],106)
        self.assertEqual(len({s["id"] for s in plan["settings"]}),106)
        for s in plan["settings"]:
            if s["kind"]=="basis_transfer":
                self.assertEqual(sum((C.from_dict(v) for v in s["ideal_probabilities"].values()),C()),C(1))
            elif s["kind"]=="cross_block_coherence":
                self.assertEqual(C.from_dict(s["ideal_plus_probability"])+C.from_dict(s["ideal_minus_probability"]),C(1))
        negative=next(s for s in plan["settings"] if s["id"]=="guard_16")
        self.assertEqual(C.from_dict(negative["ideal_guard_probability"]),C(F(1,2)))
        self.assertEqual(negative["injection_configuration"],"inserted_active")
        baseline=next(s for s in plan["settings"] if s["id"]=="guard_0")
        self.assertEqual(baseline["injection_configuration"],"physically_bypassed_or_removed")
        self.assertIn("physically bypassed or removed",plan["ordinary_guard_configuration"])
        self.assertIsNone(plan["herald_windows_per_setting"])


class PhotonicEvidenceGuards(unittest.TestCase):
    def test_loss_and_multiclick_windows_keep_original_denominator(self):
        layout=design_photonic_exchange();counts=(35,35)+(0,)*14
        r=observed_rates(layout,heralds=100,core_counts=counts,guard_count=5,no_click=20,multi_click=5)
        self.assertEqual(r["core_per_herald"],F(7,10));self.assertEqual(r["guard_per_herald"],F(1,20))
        self.assertEqual(r["no_click_per_herald"],F(1,5));self.assertEqual(r["multi_click_per_herald"],F(1,20))
        self.assertEqual(r["core_distribution_conditioned_on_core_click"][:2],(F(1,2),F(1,2)))
        self.assertEqual(r["physical_acceptance"],"NOT_ASSESSED")
        r=observed_rates(layout,heralds=10,core_counts=(0,)*16,guard_count=0,no_click=10,multi_click=0)
        self.assertIsNone(r["core_distribution_conditioned_on_core_click"])

    def test_invalid_or_incomplete_trial_counts_rejected(self):
        layout=design_photonic_exchange()
        base=dict(heralds=10,core_counts=(0,)*16,guard_count=0,no_click=10,multi_click=0)
        for changed in (dict(heralds=0),dict(heralds=True),dict(no_click=9),dict(multi_click=-1),
                        dict(core_counts=[0]*16),dict(core_counts=(False,)+(0,)*15),dict(core_counts=(0,))):
            with self.assertRaises((ValueError,TypeError)):observed_rates(layout,**(base|changed))

    def test_resource_caps_types_and_layout_tampering(self):
        for kw in (dict(grid=12),dict(grid=True),dict(pair_sum=True),dict(reference=4),dict(max_paths=True)):
            with self.assertRaises((ValueError,TypeError)):design_photonic_exchange(**kw)
        with self.assertRaises(ResourceLimit):design_photonic_exchange(max_paths=16)
        with self.assertRaises(ResourceLimit):design_photonic_exchange(grid=128)
        layout=design_photonic_exchange(max_paths=17)
        for bad in (replace(layout,pairs=layout.pairs[:-1]),replace(layout,guard=True),replace(layout,guard=15),
                    replace(layout,fixed=(False,5,10,15)),replace(layout,pairs=list(layout.pairs))):
            self.assertFalse(verify_photonic_exchange(bad))
            with self.assertRaises(ValueError):bad.netlist()
        with self.assertRaises(ValueError):layout.column(17,0)
        with self.assertRaises(TypeError):layout.column(True,0)


if __name__=="__main__":unittest.main()
