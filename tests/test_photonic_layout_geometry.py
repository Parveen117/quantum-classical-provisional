"""CAD-only tests, separate from the dependency-free calculator suite."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

try:
    import gdstk
    import klayout.db as k
except ImportError:  # CAD toolchain is optional; the calculator suite does not need it.
    gdstk = k = None
from phase_seam_foundation import photonic_layout as m


@unittest.skipUnless(gdstk is not None and k is not None, "optional CAD toolchain (gdstk, klayout) not installed")
class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);m.build_layout(self.root)
        self.path=self.root/"exchange_core.gds"

    def modified(self,layer,shape,subtract=False):
        ly=k.Layout();ly.read(str(self.path));top=ly.top_cell();idx=ly.layer(layer,0)
        if subtract:
            top.flatten(True)
            region=k.Region(top.shapes(idx))-k.Region(shape)
            top.shapes(idx).clear();top.shapes(idx).insert(region)
        else:top.shapes(idx).insert(shape)
        ly.write(str(self.path))

    def test_independent_reader_checks_geometry_and_connected_components(self):
        r=m.check_layout(self.path)
        self.assertTrue(r["passed"],r["failures"])
        self.assertEqual((r["optical_connected_components"],r["heaters"],r["pads"]),(11,28,56))
        self.assertFalse(r["foundry_drc_run"])

    def test_gds_generation_is_deterministic_and_uses_verified_macros(self):
        before=self.path.read_bytes();m.build_layout(self.root)
        self.assertEqual(before,self.path.read_bytes())
        lib=gdstk.read_gds(self.path)
        self.assertEqual(len(lib["HEATED_EXCHANGE_UNIT"].references),6)
        self.assertEqual(len(lib["CS_SIN300_MMI2X2"].polygons),1)
        self.assertEqual(len(lib["CS_SIN300_HEATER"].polygons),3)

    def test_broken_input_is_detected(self):
        self.modified(203,k.Box(1100000,662000,1102000,665000),subtract=True)
        r=m.check_layout(self.path)
        self.assertFalse(r["passed"]);self.assertEqual(r["failures"]["optical_partition"],1)

    def test_guard_short_is_detected(self):
        self.modified(203,k.Box(1200000,7200000,1201200,7600000))
        r=m.check_layout(self.path)
        self.assertFalse(r["passed"]);self.assertEqual(r["failures"]["optical_partition"],1)

    def test_pad_bridge_is_detected(self):
        # Bridge the two input-trim pads on the first unit, below its lower path.
        self.modified(41,k.Box(1110000,336000,1260000,346000))
        r=m.check_layout(self.path)
        self.assertFalse(r["passed"])
        self.assertTrue(r["failures"]["pad_count"] or r["failures"]["two_pads_per_heater"])

    def test_unexpected_layer_rejected(self):
        self.modified(999,k.Box(0,0,10000,10000))
        with self.assertRaises(ValueError):m.check_layout(self.path)

    def test_displaced_heater_is_detected(self):
        lib=gdstk.read_gds(self.path)
        ref=next(r for r in lib["HEATED_EXCHANGE_UNIT"].references if r.cell_name=="CS_SIN300_HEATER")
        x,y=ref.origin;ref.origin=(x,y-20)
        lib.write_gds(self.path)
        r=m.check_layout(self.path)
        self.assertFalse(r["passed"]);self.assertGreater(r["failures"]["heater_alignment"],0)

    def test_thin_disconnected_feature_is_detected(self):
        self.modified(203,k.Box(8000000,8000000,8100000,8000200))
        r=m.check_layout(self.path)
        self.assertFalse(r["passed"]);self.assertGreater(r["failures"]["layer_203_width"],0)

    def test_vendor_tamper_is_rejected(self):
        fake=self.root/"vendor";fake.mkdir()
        (fake/"mmi2x2.gds").write_bytes(b"corrupt")
        with patch.object(m,"VENDOR",fake):
            with self.assertRaises(ValueError):m.build_layout(self.root/"bad")


if __name__=="__main__":unittest.main()
