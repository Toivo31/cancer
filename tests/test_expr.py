"""Safe condition evaluator (pathway_sim/expr.py): grammar, equivalence with the old eval-based
guards on every shipped scenario, and a red-team list of hostile expressions."""

import ast
import copy
import glob
import itertools
import json
import pickle
import random
from pathlib import Path

import pytest
import yaml

from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate, RandomPolicy
from pathway_sim.expr import ExprError, MAX_LENGTH, names_in, parse, suggest, unknown_names
from pathway_sim.policy import PatientView, RulePolicy
from pathway_sim.scenario import scenario_from_dict

ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------------- helpers

def shipped_expressions() -> list[str]:
    """Every guard and policy rule condition in every shipped YAML scenario."""
    out: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "when" and isinstance(v, str):
                    out.add(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for f in glob.glob(str(ROOT / "scenarios" / "**" / "*.yaml"), recursive=True):
        walk(yaml.safe_load(open(f)))
    return sorted(out)


def py_eval(expr: str, env: dict):
    """The oracle: what the engine used to do (kept here only as a test reference)."""
    class Names(dict):
        def __missing__(self, key):
            return None
    return eval(compile(expr, "<oracle>", "eval"), {"__builtins__": {}}, Names(env))


# ----------------------------------------------------------------------------- shipped scenarios

def test_shipped_scenarios_give_identical_results():
    """Locks metrics and run logs of every shipped scenario x flowchart x {rule policy, random policy}
    against digests taken with the eval-based engine (tests/fixtures/guard_eval_baseline.json)."""
    import hashlib
    expected = json.loads((ROOT / "tests" / "fixtures" / "guard_eval_baseline.json").read_text())
    h = lambda o: hashlib.sha256(json.dumps(o, default=str).encode()).hexdigest()[:20]
    got = {}
    for path in sorted(glob.glob(str(ROOT / "scenarios" / "**" / "*.yaml"), recursive=True)):
        rel = str(Path(path).relative_to(ROOT))
        sc = load_scenario(path)
        for fid in sc.flowcharts:
            n = 300 if sc.id.startswith("finland") else 120
            pts = generate_patients(sc, n, 1)
            for pname, pol in (("rules", None), ("random", RandomPolicy(1))):
                run = simulate(sc, fid, pts, policy=pol, seed=1)
                m = compute_metrics(run, sc)
                got[f"{rel}|{fid}|{pname}"] = {"n": n, "run": h(run.to_dict()), "metrics": h(m),
                                               "share_within_target": m["share_within_target"],
                                               "median_days_to_treatment": m["median_days_to_treatment"],
                                               "stuck": m["stuck"], "missed_cancers": m["missed_cancers"]}
    assert got == expected


def test_every_shipped_expression_matches_python_on_all_environments():
    """Differential test: for each shipped condition, over the full product of the values its
    names can take, the new evaluator and Python's own evaluation agree on the truth value."""
    exprs = shipped_expressions()
    assert len(exprs) > 40
    values = [True, False, None, "central", "peripheral", "yes", "no", "other_biopsy", "lung_referral",
              "site_specific", "non_specific", "surgery", "radiotherapy"]
    rng = random.Random(7)
    for e in exprs:
        names = sorted(parse(e).names)
        if len(names) <= 3:
            envs = (dict(zip(names, combo)) for combo in itertools.product(values, repeat=len(names)))
        else:
            envs = (dict(zip(names, (rng.choice(values[:3] + values[3:5]) for _ in names))) for _ in range(3000))
            envs = itertools.chain(envs, (dict(zip(names, combo)) for combo in itertools.product([True, False, None], repeat=min(len(names), 7)) if len(combo) == len(names)))
        for env in envs:
            assert bool(parse(e)(env)) == bool(py_eval(e, env)), (e, env)


def test_values_not_just_truth_match_python():
    # and / or return operands, as in Python
    for e, env in [("a and b", {"a": 0, "b": "x"}), ("a or b", {"a": 0, "b": "x"}), ("a or b", {"a": "", "b": None}),
                   ("not a", {"a": "x"}), ("a and b and c", {"a": 1, "b": 2, "c": 3}), ("a or b or c", {"a": 0, "b": 0, "c": 0})]:
        assert parse(e)(env) == py_eval(e, env)


# ----------------------------------------------------------------------------- grammar

@pytest.mark.parametrize("src, env, want", [
    ("cxr", {"cxr": True}, True),
    ("cxr", {}, None),                                      # unknown names are None
    ("not cxr", {}, True),
    ("bronch is not False", {"bronch": None}, True),
    ("bronch is not False", {"bronch": False}, False),
    ("bronch is None", {}, True),
    ("x == 'a'", {"x": "a"}, True),
    ('x == "a"', {"x": "b"}, False),
    ("x != 'a'", {"x": "b"}, True),
    ("age >= 65", {"age": 65}, True),
    ("age < 65", {"age": 65}, False),
    ("50 <= age < 70", {"age": 60}, True),
    ("50 <= age < 70", {"age": 70}, False),
    ("age > -1", {"age": 0}, True),
    ("age > 1.5", {"age": 2}, True),
    ("group in ('a', 'b')", {"group": "b"}, True),
    ("group in ['a', 'b']", {"group": "c"}, False),
    ("group not in ('a', 'b')", {"group": "c"}, True),
    ("(a or b) and not c", {"a": True, "c": False}, True),
    ("True", {}, True),
    ("False", {}, False),
    ("None", {}, None),
    ("age < 65", {}, False),                                # None < 65 is False, never a crash
    ("t >= 3", {"t": None}, False),
    ("  cxr  ", {"cxr": True}, True),
    ("(\n a\n and b\n)", {"a": 1, "b": 2}, 2),
])
def test_supported_grammar(src, env, want):
    assert parse(src)(env) == want


def test_names_and_constants():
    e = parse("cxr and group == 'x' or not (age > 3 and ct is not False)")
    assert e.names == {"cxr", "group", "age", "ct"}
    assert not e.is_constant
    assert parse("False").is_constant and parse("not True").is_constant
    assert names_in("a or b") == {"a", "b"}
    assert unknown_names("cxrr and group == 'x'", ["cxr"]) == ["cxrr"]
    assert suggest("cxrr", ["cxr", "ct"]) == "cxr"
    assert suggest("zzzz", ["cxr"]) is None


def test_expr_is_immutable_cached_picklable_deepcopyable():
    e = parse("a and not b")
    assert parse("a and not b") is e                         # cached
    assert pickle.loads(pickle.dumps(e))({"a": True}) is True
    assert copy.deepcopy(e)({"a": True, "b": True}) is False
    with pytest.raises(AttributeError):
        e.source = "x"                                       # __slots__ and no dict: cannot grow attributes


def test_error_carries_position():
    with pytest.raises(ExprError) as ei:
        parse("a and open('x')")
    assert ei.value.col == 6 and "call" in ei.value.message
    with pytest.raises(ExprError) as ei:
        parse("a and and b")
    assert ei.value.col is not None


# ----------------------------------------------------------------------------- red team

HOSTILE = [
    # calls, builtins and imports
    "__import__('os').system('id')", "open('/etc/passwd')", "eval('1')", "exec('x=1')", "compile('1','','eval')",
    "getattr(a, 'b')", "print(1)", "len(a)", "type(a)", "dir()", "globals()", "locals()", "vars()", "input()",
    "breakpoint()", "(lambda: 1)()", "a(b)", "a()()",
    "import os", "from os import path", "__import__", "__builtins__", "__builtins__['eval']('1')",
    # attribute access, dunders, class walking
    "a.b", "''.join(['a'])", "().__class__", "().__class__.__bases__[0].__subclasses__()", "a.__class__",
    "a.__dict__", "(1).real", "'x'.format", "a.b.c.d", "[].__class__.__mro__", "''.__class__.__mro__[1]",
    "__class__", "__name__", "_private", "a == __x__", "__dict__",
    # subscripts and slices
    "a[0]", "a['x']", "a[1:2]", "[1,2][0]", "{'a': 1}['a']", "a[::-1]",
    # arithmetic and huge exponents (denial of service)
    "9 ** 9 ** 9", "9**9**9**9", "10 ** 100000000", "2 ** 1000000 > 1", "1 + 1", "a + b", "a * b", "'a' * 100000000",
    "[0] * 100000000", "a % b", "a // 0", "1 / 0", "-a", "+a", "~a", "a << 100000000", "a @ b",
    # lambdas, comprehensions, generators, conditional expressions
    "lambda: 1", "lambda x: x", "[x for x in range(10**9)]", "{x for x in a}", "{x: 1 for x in a}",
    "(x for x in a)", "a if b else c", "1 if True else 2",
    # containers outside `in`, dict/set displays
    "[1, 2]", "(1, 2)", "{1, 2}", "{'a': 1}", "{}", "[]", "()", "a == [1]", "a == (1, 2)", "[a, b]", "a in [b]", "a in (b,)",
    "a in b", "a in 'abc'", "a in {1: 2}", "a in [x for x in b]", "a in ([1],)", "a in ((1, 2),)",
    # `is` abuse
    "a is 'x'", "a is 1", "a is b", "a is not []", "a is ()",
    # walrus, await, yield, starred, f-strings, bytes, complex, ellipsis
    "(x := 1)", "await a", "yield a", "yield from a", "f'{a}'", "f'{__import__(\"os\")}'", "b'x'", "1j", "...", "*a", "[*a]",
    "'a' 'b' f'{c}'",
    # statements and multi-expression tricks
    "a; b", "a\nb", "x = 1", "a = 1", "del a", "pass", "return 1", "if a: b", "for x in a: pass", "while True: pass",
    "class A: pass", "def f(): pass", "assert a", "raise Exception", "with a: pass", "global a", "a, b", "a, ",
    # syntax junk and encodings
    "", "   ", "a and", "and", "(", ")", "((", "a ==", "== a", "a b", "a $ b", "a ? b", "`a`", "a <> b", "a !", "0x", "1__0",
    "a\x00b", "\x00", "a\\", "# comment", "a # comment) and __import__('os')", "a．b",
    "'unterminated", '"""unterminated', "a ::", "@", "->", "$", "a ->", "'a' if",
    # resource limits
    "a and " * 400 + "a", "(" * 500 + "a" + ")" * 500, "not " * 500 + "a", "a == " + "(" * 300 + "1" + ")" * 300,
    "'" + "x" * 5000 + "'", "a" * (MAX_LENGTH + 1), "a == '" + "y" * 300 + "'", "a in (" + ",".join("1" for _ in range(100)) + ")",
    " or ".join(f"v{i}" for i in range(400)), "1" + "0" * 40, "a == " + "9" * 20, "a == 1e400", "a < -1e400", "a == 1e30",
    # unicode confusables / non-ascii names
    "é", "naïve", "a == 'ok' and ｅｖａｌ('1')",
]


@pytest.mark.parametrize("src", HOSTILE)
def test_hostile_expression_rejected_at_parse(src):
    with pytest.raises(ExprError):
        parse(src)


def tiny_world(guard=None, rule=None):
    flow = {"nodes": [{"id": "a", "test": "ct"},
                      {"id": "x", "kind": "exit", "outcome": "treatment", "after": ["a"]}]}
    if guard is not None:
        flow["nodes"][1]["when"] = guard
    if rule is not None:
        flow["nodes"] = [{"id": "a", "test": "ct"}, {"id": "c", "kind": "choice", "after": ["a"], "options": ["p", "q"]},
                         {"id": "p", "test": "ct"}, {"id": "q", "test": "ct"},
                         {"id": "x", "kind": "exit", "outcome": "treatment", "after_any": ["p", "q"]}]
        flow["policy"] = {"c": {"rules": [{"when": rule, "choose": "p"}], "default": "q"}}
    return {"id": "t", "target_days": 30, "arrivals": {"spread_days": 10},
            "conditions": [{"id": "k", "cancer": True, "prevalence": 1.0}],
            "resources": {"r": {"type": "delay", "wait": {"dist": "fixed", "value": 1}}},
            "tests": {"ct": {"resource": "r", "p_positive": {"default": 0.5}}},
            "flowcharts": {"f": flow}}


@pytest.mark.parametrize("src", HOSTILE)
def test_hostile_expression_rejected_at_load_as_guard_and_as_policy_rule(src):
    if not src.strip():
        pytest.skip("an empty guard means no guard")
    with pytest.raises(ValueError):
        scenario_from_dict(tiny_world(guard=src))
    with pytest.raises(ValueError):
        scenario_from_dict(tiny_world(rule=src))


def test_a_good_guard_and_rule_still_load():
    scenario_from_dict(tiny_world(guard="a and group == 'all'"))
    scenario_from_dict(tiny_world(rule="a is not False"))


def test_hostile_rule_is_rejected_by_rulepolicy_directly():
    with pytest.raises(ValueError):
        RulePolicy({"c": {"rules": [{"when": "__import__('os').system('true')", "choose": "p"}]}})


def test_guard_cannot_reach_python_state():
    """Whatever a (valid) condition names, it only ever reads the environment it is given."""
    env = {"os": "env-os", "__import__": "nope"}
    assert parse("os")(env) == "env-os"
    assert parse("open")(env) is None       # an unknown name is None, not the builtin
    assert parse("print is None")(env) is True


def test_deep_nesting_does_not_crash_the_parser():
    for depth in (300, 5000, 100000):
        with pytest.raises(ExprError):
            parse("(" * depth + "a" + ")" * depth)
    for depth in (50, 5000, 100000):
        with pytest.raises(ExprError):
            parse("not " * depth + "a")
    assert parse("(" * 40 + "a" + ")" * 40)({"a": 1}) == 1       # parentheses alone add no tree depth


def test_comments_rejected_but_hash_in_text_is_fine():
    with pytest.raises(ExprError):
        parse("a # and b")
    assert parse("a == '#1'")({"a": "#1"}) is True


def test_non_ascii_names_are_normalised_by_python_not_a_bypass():
    # Python folds fullwidth and script letters to ASCII in identifiers; the name check sees the folded id
    assert parse("ａ")({"a": 5}) == 5
    assert parse("ａ").names == {"a"}


def test_big_but_legal_expression_is_fast_to_parse_and_run():
    src = " or ".join(f"v{i} == 'x'" for i in range(60))
    e = parse(src)
    assert e({f"v{i}": "x" for i in range(60)}) is True
    assert e({}) is False


def test_no_eval_exec_or_compile_of_text_left_in_the_codebase():
    """The unsafe pattern must not come back: no eval/exec and no builtin compile on strings in the engine,
    policies, scenario loader or optimiser (re.compile is fine)."""
    banned = {"eval", "exec"}
    for pkg in ("pathway_sim", "optimiser", "decision_model"):
        for f in (ROOT / pkg).rglob("*.py"):
            tree = ast.parse(f.read_text())
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    assert n.func.id not in banned | {"compile"}, f"{f}:{n.lineno} calls {n.func.id}"
