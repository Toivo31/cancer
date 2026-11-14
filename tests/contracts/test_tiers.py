"""The fast and slow tiers partition the suite, and every line of tests/slow_tests.txt still matches a test."""

import subprocess
import sys
from pathlib import Path

import conftest

ROOT = Path(__file__).resolve().parents[2]


def collect(*args) -> set[str]:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode in (0, 5), out.stdout[-2000:] + out.stderr[-2000:]  # 5: nothing selected
    return {ln for ln in out.stdout.splitlines() if "::" in ln}


def test_fast_and_slow_partition_the_full_suite():
    full, fast, slow = collect(), collect("-m", "not slow"), collect("-m", "slow")
    assert full, "collected nothing"
    assert fast | slow == full
    assert not (fast & slow)
    assert slow, "tests/slow_tests.txt marks nothing"


def test_every_slow_list_entry_matches_a_test():
    full = collect()
    entries = conftest._slow_entries()
    assert entries
    dead = [e for e in entries if not any(conftest.is_listed_slow(n, [e]) for n in full)]
    assert not dead, f"entries in tests/slow_tests.txt that match no test (renamed or deleted?): {dead}"
