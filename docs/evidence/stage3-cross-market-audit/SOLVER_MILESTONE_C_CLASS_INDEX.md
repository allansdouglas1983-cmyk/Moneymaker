# STAGE3-0006C-C-REV1 Milestone C — mutation class index

total mutation specs: 229
killed: 229
survivors: 0
non-normal: 0
untested: 0
hardening rounds: 0

## Survivor classes

- (none — 100% of mutants killed on round 1)

## Revised micro-gates

- gate 1 convergence (residual-only, inclusive): killed 18, survived 0, nonnormal 0
- gate 2 iteration budget (range semantics + increment + type refusal): killed 32, survived 0, nonnormal 0
- gate 3 Newton step (exact 2x2 Cramer + NewtonStep2 contract): killed 97, survived 0, nonnormal 0
- gate 4 clamp projection + full-step application (damping WITHDRAWN by REV1 §1): killed 38, survived 0, nonnormal 0
- gate 5 stagnation + final grid-vs-Newton selection: killed 44, survived 0, nonnormal 0
- gate 6 iteration transition + non-convergence: FROZEN_LOOP_DIFFERENTIAL + GOLDEN (8/8 exact, all termination reasons; solver.py module-wide mutation deferred to the final consolidated packet)
