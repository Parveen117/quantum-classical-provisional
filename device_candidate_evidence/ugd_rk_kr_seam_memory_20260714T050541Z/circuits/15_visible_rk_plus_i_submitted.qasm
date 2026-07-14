OPENQASM 3.0;
include "stdgates.inc";
bit[2] c;
rz(pi/2) $1;
sx $1;
c[0] = measure $0;
c[1] = measure $1;
