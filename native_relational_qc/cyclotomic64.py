"""Compatibility alias of the shared flat field; historical JSON is retained."""
from .legacy_cyclotomic import legacy_field_of_order, BASES

Cyclotomic64 = legacy_field_of_order(64)
BASIS = BASES[64]
ZERO, ONE, ZETA = Cyclotomic64(), Cyclotomic64(1), Cyclotomic64.root()
