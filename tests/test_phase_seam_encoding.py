"""Bridge tests: exact tomography, supported channels and a negative witness."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import unittest

from phase_seam_foundation import Cell, Config, Operation as Op
from phase_seam_foundation.encoding import (
    C,ZERO,ONE,Exact,Op64,I,XA,YA,ZA,XB,YB,ZB,PAIRS,SEAM,ROOTS,
    density,positive_factors,decode,encode,recover,verify_bridge,ledger_update,
    compile_transport,verify_transport,transport_unitary,channel_obstruction,
    phase_pair,binary_readout,UnsupportedTransport,ResourceLimit)
from phase_seam_foundation.joint import Element,bell_preparation,bell_settings,chsh,interaction


def mm(a,b):
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(len(b))),ZERO)
                       for j in range(len(b[0]))) for i in range(len(a)))


def dagger(a):
    return tuple(tuple(a[j][i].conjugate() for j in range(len(a))) for i in range(len(a[0])))


def dense(operator):
    # Independent 2x2 matrices; runtime encoding never calls this.
    blocks=(((1,0),(0,1)),((1,0),(0,-1)),((0,-1),(1,0)),((0,1),(1,0)))
    out=[[ZERO]*4 for _ in range(4)]
    for k,x in enumerate(operator.coefficients):
        if not x:continue
        for i,j in product(range(4),repeat=2):
            out[i][j]+=x*blocks[k%4][i%2][j%2]*blocks[k//4][i//2][j//2]
    return tuple(map(tuple,out))


def trace(a):
    return sum((a[i][i] for i in range(len(a))),ZERO)


class EncodingAlgebraTests(unittest.TestCase):
    def test_all_256_products_embed_previous_algebra(self):
        for i,j in product(range(16),repeat=2):
            a,b=Op64.basis(i),Op64.basis(j)
            self.assertEqual(a*b,Op64.from_joint(Element.basis(2,i)*Element.basis(2,j)))
        for i in range(16):
            a=Op64.basis(i)
            self.assertEqual(dense(a.dagger()),dagger(dense(a)))

    def test_nonlegacy_phase_product_against_independent_matrices(self):
        a=I+XA*ROOTS[1]+YA*ROOTS[11]+SEAM*F(2,3)
        b=XB*ROOTS[7]+ZA*ROOTS[15]+ZB*ROOTS[9]
        self.assertEqual(dense(a*b),mm(dense(a),dense(b)))
        self.assertEqual((a*b).dagger(),b.dagger()*a.dagger())

    def test_nine_readings_are_orthogonal_and_each_pair_anticommutes(self):
        bank=tuple(x for pair in PAIRS for x in pair)+(SEAM,)
        for i,a in enumerate(bank):
            self.assertEqual(a*a,I)
            self.assertEqual(a.dagger(),a)
            self.assertEqual(a.tau(),ZERO)
            for j,b in enumerate(bank):
                self.assertEqual((a*b).tau(),ONE if i==j else ZERO)
        for p,q in PAIRS:
            self.assertEqual(p*q,-q*p)

    def test_all_64_phase_pairs_unit_circle(self):
        for r in range(64):
            u,v=phase_pair(64,r)
            self.assertEqual(u*u+v*v,ONE)
            self.assertEqual(u.conjugate(),u)
            self.assertEqual(v.conjugate(),v)
            self.assertEqual(u+v*Exact(c=1),ROOTS[r])

    def test_positive_square_decomposition_and_normalization(self):
        for gamma in (F(1,7),F(1),F(8,3)):
            phases=(1,13,38,63)
            d=density(phases,gamma)
            factors=positive_factors(phases,gamma)
            rebuilt=I*0
            for w,s in factors:
                self.assertGreater(w,0)
                self.assertEqual(s*s,s)
                self.assertEqual(s.dagger(),s)
                rebuilt=rebuilt+(s*s.dagger())*w
            self.assertEqual(rebuilt,d)
            self.assertEqual(d.tau(),ONE)
            self.assertEqual(d.dagger(),d)

    def test_strict_types_and_field_bound(self):
        for call in (lambda:Op64.basis(True),lambda:Op64((0,)*15),
                     lambda:Op64((0.5,)+(0,)*15),lambda:phase_pair(12,1),
                     lambda:phase_pair(64,True),lambda:density((0,0,0,0),0),
                     lambda:density((0,0,0,0),0.5)):
            with self.assertRaises((TypeError,ValueError)):call()
        with self.assertRaises(ResourceLimit): I*(2**4096)
        a=I*(2**2048)
        with self.assertRaises(ResourceLimit): a*a
        self.assertEqual(a.coefficients[0],C(2**2048))


class TomographicBridgeTests(unittest.TestCase):
    def test_all_64_phases_in_each_of_four_modes_roundtrip(self):
        for mode,r in product(range(4),range(64)):
            phases=[0,17,31,63]; phases[mode]=r
            phases=tuple(phases); gamma=F(7,3)
            d=density(phases,gamma)
            self.assertEqual(decode(d),(phases,gamma))
            u,v=phase_pair(64,r)
            self.assertEqual(d.expect(PAIRS[mode][0])*5,u)
            self.assertEqual(d.expect(PAIRS[mode][1])*5,v)

    def test_all_supported_grids_and_seam_duality(self):
        for grid,gamma in product((4,8,16,32,64),(F(1,17),F(1),F(23,2))):
            phases=(1%grid,2%grid,3%grid,0)
            d=density(phases,gamma,grid)
            self.assertEqual(decode(d,grid),(phases,gamma))
            t=(gamma-1)/(gamma+1)
            self.assertEqual(d.expect(SEAM),C(t/5))
            dual=density(phases,1/gamma,grid)
            self.assertEqual(dual.expect(SEAM),-d.expect(SEAM))

    def test_global_phase_shift_is_retained_in_this_moment_encoding(self):
        a=density((0,0,0,0),1)
        b=density((1,1,1,1),1)
        self.assertNotEqual(a,b)
        self.assertNotEqual(a.expect(PAIRS[0][1]),b.expect(PAIRS[0][1]))

    def test_reconstruct_full_cell_history_with_cost_readout_reset(self):
        x=Cell.start((71,-9,3,4),gamma=F(2,3))
        for op in (Op("cut",(0,7)),Op("shear",(2,1,-2,1)),
                   Op("read",(0,3)),Op("reset",(2,4)),Op("pair_shift",(0,2,64))):
            x=x.apply(op)
        bridge=encode(x)
        self.assertTrue(verify_bridge(bridge))
        self.assertEqual(recover(bridge),x)
        self.assertEqual(recover(bridge).events[-3].outcome,x.events[-3].outcome)

    def test_winding_and_order_remain_in_classical_tape(self):
        x=Cell.start((1,0,0,0))
        a=x.apply(Op("shift",(0,64)))
        b=x.apply(Op("shift",(0,-64)))
        ba,bb=encode(a),encode(b)
        self.assertEqual(ba.code,bb.code)
        self.assertNotEqual(ba.operations,bb.operations)
        self.assertEqual(recover(ba),a)
        self.assertEqual(recover(bb),b)
        c=x.apply(Op("cut",(0,0))).apply(Op("cut",(0,0)))
        self.assertEqual(encode(c).code,encode(x).code)
        self.assertNotEqual(c.state.cost,x.state.cost)
        self.assertNotEqual(encode(c),encode(x))

    def test_tampered_tape_code_and_outside_family_rejected(self):
        b=encode(Cell.start((1,2,3,4)))
        bad=replace(b,code=density((2,2,3,4),1))
        self.assertFalse(verify_bridge(bad))
        self.assertFalse(verify_bridge(replace(b,operations=(Op("shift",(0,1)),))))
        with self.assertRaises(ValueError):decode(b.code+(XA*XB)/100)
        with self.assertRaises(ValueError):decode(b.code*2)
        with self.assertRaises(ValueError):decode(I+SEAM/5)
        with self.assertRaises(ValueError):decode(density((1,0,0,0),1),32)

    def test_invalid_source_or_grid_and_resource_are_atomic(self):
        x=Cell.start((1,0,0,0))
        with self.assertRaises(ValueError):encode(replace(x,state=Cell.start().state))
        with self.assertRaises(ValueError):encode(Cell.start(config=Config(grid=12)))
        x=Cell.start(config=Config(max_events=1))
        b=encode(x)
        with self.assertRaises(ResourceLimit):
            ledger_update(b,(Op("shift",(0,1)),Op("shift",(0,1))))
        self.assertEqual(recover(b),x)
        y=Cell.start(config=Config(sector=1))
        with self.assertRaises(ValueError):ledger_update(encode(y),(Op("shift",(0,1)),))
        self.assertEqual(recover(encode(y)),y)

    def test_single_readout_statistics_do_not_return_exact_phase_label(self):
        d=density((0,0,0,0),1)
        self.assertEqual(binary_readout(d,PAIRS[0][0]),{-1:C(F(2,5)),1:C(F(3,5))})
        self.assertEqual(binary_readout(d,I),{-1:ZERO,1:ONE})
        with self.assertRaises(ValueError):binary_readout(d,I/2)
        # Even a perfectly known phase gives both +/- outcomes in this encoding.
        self.assertEqual(decode(d)[0],(0,0,0,0))


class IntertwiningTests(unittest.TestCase):
    def test_all_64_balanced_transport_angles(self):
        cell=Cell.start((1,8,19,-28),config=Config(sector=1),gamma=F(5,2))
        bridge=encode(cell)
        for delta in range(64):
            ops=(Op("pair_shift",(0,2,delta)),)
            cert=compile_transport(bridge,ops)
            self.assertEqual(recover(cert.after),cell.apply(ops[0]))
            self.assertEqual(cert.unitary*bridge.code*cert.unitary.dagger(),cert.after.code)
            self.assertEqual(cert.unitary.dagger()*cert.unitary,I)
        self.assertTrue(verify_transport(cert))

    def test_both_pairs_reverse_directions_and_subgrids(self):
        for grid,pair in product((4,8,16,32,64),((0,2),(2,0),(1,3),(3,1))):
            x=Cell.start((1,2,3,-6),config=Config(grid=grid,sector=1),gamma=F(2,7))
            op=Op("pair_shift",(*pair,3))
            cert=compile_transport(encode(x),(op,))
            self.assertEqual(recover(cert.after),x.apply(op))
            inverse=compile_transport(cert.after,(op.inverse(),))
            self.assertEqual(inverse.after.code,cert.before.code)
            self.assertNotEqual(inverse.after.operations,cert.before.operations)

    def test_site_swap_intertwining_and_independent_matrix_permutation(self):
        x=Cell.start((1,8,19,-28),config=Config(sector=1),gamma=F(2,3))
        ops=(Op("swap",(0,1)),Op("swap",(2,3)))
        for word in (ops,ops[::-1]):
            cert=compile_transport(encode(x),word)
            self.assertTrue(verify_transport(cert))
            expected=tuple(tuple(C(int(j==((i%2)*2+i//2))) for j in range(4)) for i in range(4))
            self.assertEqual(dense(cert.unitary),expected)
            self.assertEqual(dense(cert.after.code),mm(mm(expected,dense(cert.before.code)),dagger(expected)))

    def test_transport_replay_and_operator_tampering_rejected(self):
        b=encode(Cell.start((1,2,3,-6),config=Config(sector=1)))
        cert=compile_transport(b,(Op("pair_shift",(0,2,1)),))
        self.assertTrue(verify_transport(cert))
        self.assertFalse(verify_transport(replace(cert,unitary=I)))
        self.assertFalse(verify_transport(replace(cert,after=cert.before)))
        self.assertFalse(verify_transport(replace(cert,operations=(Op("pair_shift",(0,2,2)),))))

    def test_unsupported_words_have_no_silent_reprepare_fallback(self):
        x=Cell.start()
        b=encode(x)
        for op in (Op("cut",(0,1)),Op("pair_cut",(0,2,0)),Op("shear",(0,1,1,0)),
                   Op("reset",(0,1)),Op("swap",(0,1)),Op("pair_shift",(0,1,1))):
            with self.assertRaises(UnsupportedTransport):compile_transport(b,(op,))
        # Re-encoding a known classical state is available under a separate API.
        op=Op("pair_cut",(0,2,1))
        out=ledger_update(b,(op,))
        self.assertEqual(recover(out),x.apply(op))
        self.assertEqual(recover(b),x)

    def test_dense_phase_gate_uses_no_half_grid_extension(self):
        for pair in ((0,2),(1,3)):
            u=transport_unitary((Op("pair_shift",(*pair,1)),),64)
            site=0 if pair==(0,2) else 1
            expected=tuple(tuple((ROOTS[1] if (i>>site)&1 else ONE) if i==j else ZERO
                                 for j in range(4)) for i in range(4))
            self.assertEqual(dense(u),expected)


class BoundaryTests(unittest.TestCase):
    def test_balanced_cut_channel_obstruction_with_exact_spectral_resolution(self):
        witness=channel_obstruction()
        a=(XA-YA)*Exact(b=F(1,2))
        b=(XB+YB)*Exact(b=F(1,2))
        delta=(XA-YA+XB+YB)/20
        rebuilt=I*0; absolute=I*0
        projectors=[]
        for sa,sb in product((-1,1),repeat=2):
            p=((I+a*sa)/2)*((I+b*sb)/2)
            value=Exact(b=F(sa+sb,20))
            self.assertEqual(p*p,p)
            self.assertEqual(p.tau(),C(F(1,4)))
            self.assertEqual(delta*p,p*value)
            rebuilt=rebuilt+p*value
            absolute=absolute+p*(value if sa+sb>=0 else -value)
            projectors.append(p)
        self.assertEqual(rebuilt,delta)
        distance=absolute.tau()*2  # Tr(|delta|)/2, Tr = 4 tau
        self.assertEqual(distance,witness["input_trace_distance"])
        self.assertEqual(witness["output_binary_tv"],C(F(1,5)))
        self.assertGreater((witness["output_binary_tv"]-distance).real_sign(),0)

    def test_encoding_purity_and_global_unitary_invariance(self):
        for gamma in (F(1,9),F(1),F(9)):
            t=(gamma-1)/(gamma+1)
            d=density((1,13,27,54),gamma)
            purity=(d*d).tau()/4
            self.assertEqual(purity,C(F(1,4)+F(4+t*t,100)))
            self.assertLess(purity.real_bounds(20)[1],F(3,10))
            u=Op64.from_joint(interaction())
            after=u*d*u.dagger()
            self.assertEqual((after*after).tau()/4,purity)
        bell=Op64.from_joint(bell_preparation().density)
        self.assertEqual((bell*bell).tau()/4,ONE)
        with self.assertRaises(ValueError):decode(bell)

    def test_hilbert_schmidt_bell_bound_and_two_site_reference_readout(self):
        d=density((1,13,27,54),F(2,3))
        s=Op64.from_joint(chsh(bell_settings()))
        self.assertEqual(s.tau(),ZERO)
        self.assertEqual((s*s).tau(),C(4))
        t=F(-1,5)
        radius2=((d-I)*(d-I)).tau()
        self.assertEqual(radius2,C(F(4+t*t,25)))
        value=d.expect(s)
        self.assertGreaterEqual((radius2*4-value*value).real_sign(),0)
        self.assertLess((radius2*4).real_bounds(20)[1],F(4,5))

if __name__=="__main__":
    unittest.main()
