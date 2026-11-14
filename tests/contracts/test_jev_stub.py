"""JEV contract (spec 02) against the in-process stub server.

Re-exports the checks of tests/test_jev_contract.py so ``pytest tests/contracts`` covers them; the real file stays
the one a JEV owner runs against their own service (``--jev-url``). Takes about a second."""

import test_jev_contract as _c  # tests/ is on pythonpath

target = _c.target  # the module-scoped fixture (stub server unless --jev-url is given)
globals().update({n: f for n, f in vars(_c).items() if n.startswith("test_") and callable(f)})
