"""Compatibility alias of the shared flat field; historical JSON is retained."""
from .legacy_cyclotomic import legacy_field_of_order, BASES

Cyclotomic = legacy_field_of_order(16)
BASIS = BASES[16]
ZERO, ONE, ZETA = Cyclotomic(), Cyclotomic(1), Cyclotomic.root()
