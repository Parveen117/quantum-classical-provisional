OPENQASM 3.0;
include "stdgates.inc";
bit[2] c;
x $1;
rz(-pi) $1;
c[0] = measure $0;
c[1] = measure $1;
