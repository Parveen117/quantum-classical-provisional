OPENQASM 3.0;
include "stdgates.inc";
gate rzz(p0) _gate_q_0, _gate_q_1 {
  cx _gate_q_0, _gate_q_1;
  rz(p0) _gate_q_1;
  cx _gate_q_0, _gate_q_1;
}
bit[4] c;
qubit[4] q;
h q[0];
h q[1];
h q[2];
h q[3];
barrier q[0], q[1], q[2], q[3];
rzz(1.5353981633974483) q[1], q[2];
rzz(1.0153981633974483) q[2], q[3];
rzz(1.2553981633974483) q[3], q[1];
rzz(pi/3) q[3], q[1];
barrier q[0], q[1], q[2], q[3];
h q[0];
h q[1];
h q[2];
h q[3];
c[0] = measure q[0];
c[1] = measure q[1];
c[2] = measure q[2];
c[3] = measure q[3];
