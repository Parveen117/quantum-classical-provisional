"""Exact operator identities, coherent references, and failed protection claims."""
from fractions import Fraction as Q
from itertools import product
import random
import unittest

from native_relational_qc.cyclotomic64 import ZETA, ONE, ZERO
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.weyl_bus import (
    DIMENSIONS, Pulse, normal_form, certificate, rectangle, echoed_rectangle,
    fault_certificate, native_interaction_bridge,
)

ROOTS = tuple(ZETA**j for j in range(64))


def direct_basis(word, data, k, d):
    """Apply each primitive directly to a basis label and exact amplitude.

    This uses the current bus label, not the normal-form composition rule.
    """
    amplitude = ONE
    for p in word:
        if p.kind.startswith("bus_"):
            sign = 1 if p.control is None else 1-2*((data >> p.control) & 1)
            if p.kind == "bus_x": k = (k + sign*p.steps) % d
            else: amplitude *= ROOTS[((64//d)*p.steps*sign*k) % 64]
        elif p.kind.startswith("flip_"):
            data ^= 1 if p.kind == "flip_a" else 2
        else:
            bit = data & 1 if p.kind == "phase_a" else data >> 1
            amplitude *= ROOTS[(p.steps*(1-2*bit)) % 64]
    return data, k, amplitude


class WeylBusTests(unittest.TestCase):
    def test_all_5460_rectangles_on_supported_dimensions(self):
        cases = 0
        for d in DIMENSIONS:
            for a, b in product(range(d), repeat=2):
                blocks = normal_form(rectangle(a,b), dimension=d)
                for data, v in enumerate(blocks):
                    parity = (1-2*(data&1)) * (1-2*(data>>1))
                    self.assertEqual((v.data_out,v.shift,v.clock,v.phase),
                                     (data,0,0,((64//d)*a*b*parity)%64))
                cases += 1
        self.assertEqual(cases,5460)

    def test_all_256_basis_columns_against_direct_execution(self):
        words = (rectangle(), echoed_rectangle(drift=(7,-11)),
                 rectangle()[:-1], tuple(reversed(rectangle())))
        for word in words:
            blocks = normal_form(word)
            for data,k in product(range(4),range(64)):
                v = blocks[data]
                self.assertEqual(direct_basis(word,data,k,64),
                                 (v.data_out,(k+v.shift)%64,ROOTS[(v.phase+v.clock*k)%64]))

    def test_random_mixed_words_not_only_rectangular_fixtures(self):
        rng = random.Random(7341)
        choices = ("bus_x","bus_z","phase_a","phase_b","flip_a","flip_b")
        for d in DIMENSIONS:
            for trial in range(8):
                word=[]
                for _ in range(11):
                    kind=rng.choice(choices)
                    word.append(Pulse(kind,1 if kind.startswith("flip_") else rng.randrange(-9,10),
                                      rng.choice((None,0,1)) if kind.startswith("bus_") else None))
                blocks=normal_form(word,dimension=d)
                for data,k in product(range(4),range(d)):
                    v=blocks[data]
                    self.assertEqual(direct_basis(word,data,k,d),
                                     (v.data_out,(k+v.shift)%d,ROOTS[(v.phase+(64//d)*v.clock*k)%64]))

    def test_entanglement_criterion_and_maximal_output(self):
        record=certificate(rectangle())
        self.assertTrue(record["bus_returned"])
        self.assertEqual(record["nonlocal_phase_steps"],32)
        self.assertEqual(record["plus_input_concurrence_squared"],ONE.to_dict())
        phases=[ROOTS[v.phase]/2 for v in normal_form(rectangle())]
        # Reduced A density of the coherent |++> output is I/2.
        for a,c in product(range(2),repeat=2):
            rho=sum((phases[a+2*b]*phases[c+2*b].conjugate() for b in range(2)),ZERO)
            self.assertEqual(rho,ONE/2 if a==c else ZERO)
        self.assertFalse(certificate(rectangle(4,4))["entangling"])
        self.assertFalse(certificate(rectangle(0,4))["entangling"])

    def test_bus_entangled_with_external_reference_is_preserved(self):
        # Arbitrary complex normalized bus-reference preparation: two disjoint
        # states for R=0 and two for R=1, including nontrivial relative phases.
        bus={(0,0):ONE/2,(7,0):ROOTS[3]/2,(23,1):ROOTS[17]/2,(63,1):ROOTS[29]/2}
        initial={(data,k,r):v/2 for data in range(4) for (k,r),v in bus.items()}
        actual={}
        for (data,k,r),v in initial.items():
            out,q,phase=direct_basis(rectangle(),data,k,64)
            actual[out,q,r]=v*phase
        expected={(data,k,r):v*ROOTS[8*(1-2*(data&1))*(1-2*(data>>1))%64]
                  for (data,k,r),v in initial.items()}
        self.assertEqual(actual,expected)
        for (k,r),(q,s) in product(bus,repeat=2):
            reduced=sum((actual[data,k,r]*actual[data,q,s].conjugate() for data in range(4)),ZERO)
            self.assertEqual(reduced,bus[k,r]*bus[q,s].conjugate())

    def test_local_filters_and_shared_mixtures_stay_separable(self):
        # Independent complex local filtering can change success probability,
        # but cannot turn a product amplitude matrix into rank two.
        psi=(ONE,ROOTS[3]); phi=(ONE,ROOTS[7])
        filters=(((ONE,ZERO),(ZERO,ONE/3)),((ONE,ONE/2),(ZERO,ROOTS[8]/4)))
        for left,right in product(filters,repeat=2):
            a=[sum((left[i][j]*psi[j] for j in range(2)),ZERO) for i in range(2)]
            b=[sum((right[i][j]*phi[j] for j in range(2)),ZERO) for i in range(2)]
            amplitudes=[a[i]*b[j] for j in range(2) for i in range(2)]
            self.assertEqual(amplitudes[0]*amplitudes[3]-amplitudes[1]*amplitudes[2],ZERO)
        # Convex mixing remains a sum of these product projectors (doc proof);
        # no postselected joint projection is silently supplied here.

    def test_equal_drift_echo_cancels_and_preserves_gate(self):
        expected=normal_form(rectangle())
        for a,b in ((0,0),(1,31),(-64,64),(17,-9),(4096,-4096)):
            self.assertEqual(normal_form(echoed_rectangle(drift=(a,b))),expected)
        record=certificate(echoed_rectangle())
        self.assertEqual(record["controlled_bus_pulses"],8)
        self.assertEqual(record["local_flip_pulses"],4)

    def test_unequal_drift_and_wrong_area_are_not_cancelled(self):
        ideal=normal_form(rectangle())
        actual=normal_form(echoed_rectangle(drift=(5,7),second_drift=(6,10)))
        for data,(a,i) in enumerate(zip(actual,ideal)):
            self.assertEqual((a.phase-i.phase)%64,(-(1-2*(data&1))-3*(1-2*(data>>1)))%64)
        self.assertNotEqual(normal_form(echoed_rectangle(2,4)),ideal)
        self.assertFalse(certificate(echoed_rectangle(2,4))["entangling"])

    def test_exact_fault_propagation_all_20480_single_weyl_cases(self):
        word=rectangle(); ideal=normal_form(word); count=0
        for after,x,z in product(range(5),range(64),range(64)):
            faulty=word[:after]+(Pulse("bus_z",z),Pulse("bus_x",x))+word[after:]
            blocks=normal_form(faulty)
            ca,cb=((0,0),(2*z,0),(2*z,-4*x),(0,-4*x),(0,0))[after]
            for data,(f,i) in enumerate(zip(blocks,ideal)):
                self.assertEqual((f.data_out,f.shift,f.clock),(data,x,z))
                self.assertEqual((f.phase-i.phase)%64,(ca*(1-2*(data&1))+cb*(1-2*(data>>1)))%64)
            count+=1
        self.assertEqual(count,20480)

    def test_bus_fault_witnesses_and_boundary_immunity(self):
        for seam in (0,4):
            self.assertTrue(fault_certificate(rectangle(),after=seam,x=5,z=9)["data_unchanged_up_to_global_phase"])
        mid=fault_certificate(rectangle(),after=2,x=1,z=1)
        self.assertFalse(mid["data_unchanged_up_to_global_phase"])
        self.assertEqual(mid["nonlocal_error_steps"],0)
        self.assertEqual(mid["local_one_phase_steps"],[60,8])
        # Echo does not remove a single time-local bus fault.
        self.assertFalse(fault_certificate(echoed_rectangle(),after=1,z=1)["data_unchanged_up_to_global_phase"])

    def test_full_weyl_fault_immunity_forces_nonentangling_rectangle(self):
        for d in DIMENSIONS:
            for a,b in product(range(d),repeat=2):
                all_faults_harmless=(2*a)%d==0 and (2*b)%d==0
                if all_faults_harmless:
                    self.assertEqual((4*a*b)%d,0)
                if (4*a*b)%d:
                    self.assertFalse(all_faults_harmless)

    def test_minimum_dimension_is_for_this_control_family_only(self):
        bare=[]; echoed=[]
        for d in DIMENSIONS:
            if any((4*a*b)%d==d//2 for a,b in product(range(d),repeat=2)): bare.append(d)
            if any((8*a*b)%d==d//2 for a,b in product(range(d),repeat=2)): echoed.append(d)
        self.assertEqual(min(bare),8)
        self.assertEqual(min(echoed),16)
        self.assertEqual(certificate(rectangle(1,1),dimension=8)["nonlocal_phase_steps"],32)

    def test_bad_closure_and_common_transport_are_distinguished(self):
        damaged=rectangle()[:-1]
        bad=certificate(damaged)
        self.assertFalse(bad["data_bus_factorized"])
        self.assertIsNone(bad["entangling"])
        for data in range(4):
            self.assertEqual(direct_basis(damaged,data,0,64),direct_basis(rectangle(),data,0,64))
        self.assertNotEqual(direct_basis(damaged,0,1,64),direct_basis(rectangle(),0,1,64))
        with self.assertRaises(ValueError): fault_certificate(damaged,after=1)
        common=certificate(rectangle()+(Pulse("bus_x",3),))
        self.assertTrue(common["data_bus_factorized"])
        self.assertFalse(common["bus_returned"])
        self.assertEqual(common["common_bus_word"],[3,0])

    def test_native_bridge_reuses_old_interaction_and_bell_law(self):
        from phase_seam_foundation.joint import Element, product_reference, bell_preparation, bell_settings, chsh
        bridge=native_interaction_bridge(); c=bridge["basis_change"]
        self.assertEqual(c*c.dagger(),Element.basis(2))
        state=product_reference().unitary(bridge["native_gate"])
        self.assertEqual(state.density,bell_preparation().density)
        self.assertEqual(state.expect(chsh(bell_settings())),bell_preparation().expect(chsh(bell_settings())))

    def test_invalid_inputs_and_resource_limits_fail_closed(self):
        for d in (True,0,3,128,64.0):
            with self.assertRaises(ValueError): normal_form((),dimension=d)
        for n in (True,1.5,Q(1,2),4097):
            with self.assertRaises(ValueError): rectangle(n,1)
        for args in (("unknown",),("flip_a",2),("phase_a",1,0),("bus_x",1,True)):
            with self.assertRaises(ValueError): Pulse(*args)
        with self.assertRaises(ValueError): normal_form(iter(()))
        with self.assertRaises(ValueError): normal_form((object(),))
        with self.assertRaises(ValueError): echoed_rectangle(drift=(1,))
        with self.assertRaises(ValueError): fault_certificate(rectangle(),after=5)
        with self.assertRaises(ResourceLimit): normal_form((Pulse("bus_x"),)*513)
        self.assertEqual(len(normal_form((Pulse("bus_x"),)*512)),4)


if __name__ == "__main__": unittest.main()
