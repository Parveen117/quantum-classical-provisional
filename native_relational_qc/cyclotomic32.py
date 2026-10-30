"""Compatibility alias of the shared flat field; historical JSON is retained."""
from .legacy_cyclotomic import legacy_field_of_order, BASES

Cyclotomic32 = legacy_field_of_order(32)
BASIS = BASES[32]
ZERO, ONE, ZETA = Cyclotomic32(), Cyclotomic32(1), Cyclotomic32.root()
