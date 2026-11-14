"""Population model for the background of synthetic patients (review w7, M4).

    from patient_engine.population import get_model
    model = get_model(catalogue)          # None when no populations/<catalogue id>.yaml exists
    bg = model.draw_background(seed, index, k, fields)
    shares = model.condition_shares(bg)   # P(condition | smoking status, age band), catalogue-consistent

The model lives OUTSIDE the catalogue (``populations/<id>.yaml``), so the locked catalogue hash does not
change: ``catalogue.version_hash`` is built from the five catalogue files only. The file is read explicitly here.

What it does
  * age of presenters: a right-tailed distribution by 5-year band (per mille in the file);
  * smoking status by age band and sex (Finnish pattern), scaled (raked) so the overall mix equals the mix the
    catalogue assumed when it derived the prevalence levels (never 0.40, former 0.38, current 0.22);
  * pack-years from status and age (years smoked times packs a day, so always possible for the age);
  * a relative risk by age for each condition, applied on top of the catalogue's prevalence per smoking level and
    renormalised (iterative proportional fitting) so that, within each smoking level, each condition's overall
    share stays the catalogue's number and every cell of (smoking status, age band) sums to 1.

Everything is deterministic: the numbers come from ``pathway_sim.dists.uniform`` keyed by seed, patient index and
field, like the rest of the skeleton (invariant I3). Standard library and PyYAML.
"""

from __future__ import annotations

import bisect
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping, Sequence

import yaml

from pathway_sim.dists import uniform

__all__ = ["PopulationModel", "get_model", "population_path", "PopulationError", "STATUSES"]

REPO = Path(__file__).resolve().parent.parent
POPULATIONS = REPO / "populations"
STATUSES = ("never", "former", "current")
_N = NormalDist()


class PopulationError(ValueError):
    """The population file is unreadable or inconsistent with the catalogue."""


def population_path(catalogue_id: str) -> Path:
    return POPULATIONS / f"{catalogue_id}.yaml"


def _pick(probs: Sequence[float], u: float) -> int:
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if u < acc:
            return i
    return len(probs) - 1


def _ppf(u: float) -> float:
    return _N.inv_cdf(min(max(u, 1e-9), 1 - 1e-9))


def _lognormal(median: float, sd: float, u: float) -> float:
    return math.exp(math.log(median) + sd * _ppf(u))


class PopulationModel:
    def __init__(self, spec: Mapping[str, Any], catalogue) -> None:
        self.spec = spec
        self.catalogue = catalogue
        edges = [int(x) for x in spec["age"]["edges"]]
        pm = [float(x) for x in spec["age"]["per_mille"]]
        if len(pm) != len(edges) - 1:
            raise PopulationError("age.per_mille needs one number per band")
        tot = sum(pm)
        self.edges = edges
        self.w = [x / tot for x in pm]
        self.nb = len(self.w)
        self.sex_p = {k: float(v) for k, v in spec["sex"].items()}
        s = sum(self.sex_p.values())
        self.sex_p = {k: v / s for k, v in self.sex_p.items()}
        self.sexes = tuple(self.sex_p)
        reg = {k: float(v) for k, v in spec["region"].items()}
        s = sum(reg.values())
        self.region_p = {k: v / s for k, v in reg.items()}
        self.target = [float(spec["smoking_mix"][s]) for s in STATUSES]
        self._build_smoking()
        self._build_conditions()
        self.limits = dict(spec.get("limits", {}))

    # ------------------------------------------------------------------ bands
    def band(self, age: float) -> int:
        return min(max(bisect.bisect_right(self.edges, age) - 1, 0), self.nb - 1)

    def _coarse(self, b: int) -> int:
        mid = (self.edges[b] + self.edges[b + 1]) / 2
        for i, (lo, hi) in enumerate(self.spec["smoking_by_age_sex"]["bands"]):
            if lo <= mid < hi:
                return i
        return len(self.spec["smoking_by_age_sex"]["bands"]) - 1

    # ------------------------------------------------------------------ smoking
    def _build_smoking(self) -> None:
        tab = self.spec["smoking_by_age_sex"]
        raw = {sx: [[float(x) for x in row] for row in tab[sx]] for sx in self.sexes}
        for sx in self.sexes:
            for row in raw[sx]:
                t = sum(row)
                row[:] = [x / t for x in row]
        # rake: multiply each status by a constant until the overall mix equals the target
        m = [1.0, 1.0, 1.0]
        for _ in range(300):
            marg = [0.0, 0.0, 0.0]
            for sx in self.sexes:
                for b in range(self.nb):
                    row = raw[sx][self._coarse(b)]
                    z = sum(row[i] * m[i] for i in range(3))
                    for i in range(3):
                        marg[i] += self.w[b] * self.sex_p[sx] * row[i] * m[i] / z
            m = [m[i] * self.target[i] / marg[i] for i in range(3)]
        self.raking = m
        self.p_smoke: dict[str, list[list[float]]] = {}
        for sx in self.sexes:
            rows = []
            for row in raw[sx]:
                z = sum(row[i] * m[i] for i in range(3))
                rows.append([row[i] * m[i] / z for i in range(3)])
            self.p_smoke[sx] = rows

    def smoking_probs(self, age: float, sex: str) -> list[float]:
        return self.p_smoke[sex][self._coarse(self.band(age))]

    # ------------------------------------------------------------------ conditions
    def _catalogue_shares(self, status: str) -> dict[str, float]:
        x = {c: max(0.0, float(cond.prevalence.resolve({"smoking_status": status})))
             for c, cond in self.catalogue.conditions.items()}
        t = sum(x.values())
        return {c: v / t for c, v in x.items()}

    def _rr(self, cond: str, b: int) -> float:
        d = self.spec["age_relative_risk"].get(cond)
        if d is None:
            return 1.0
        ages = [25 + 10 * i for i in range(len(d["rr"]))]
        x = (self.edges[b] + self.edges[b + 1]) / 2
        if x <= ages[0]:
            return float(d["rr"][0])
        if x >= ages[-1]:
            return float(d["rr"][-1])
        i = bisect.bisect_right(ages, x) - 1
        f = (x - ages[i]) / (ages[i + 1] - ages[i])
        return math.exp((1 - f) * math.log(d["rr"][i]) + f * math.log(d["rr"][i + 1]))

    def _build_conditions(self) -> None:
        conds = list(self.catalogue.conditions)
        self.conds = conds
        #: pop_b[s][b] = P(age band | smoking status s), over sexes
        self.pop_b: list[list[float]] = []
        for si in range(3):
            v = [sum(self.w[b] * self.sex_p[sx] * self.p_smoke[sx][self._coarse(b)][si] for sx in self.sexes)
                 for b in range(self.nb)]
            t = sum(v)
            self.pop_b.append([x / t for x in v])
        #: Q[s][b][c] = P(condition c | smoking status s, age band b)
        self.Q: list[list[dict[str, float]]] = []
        self.max_fit_error = 0.0
        for si, status in enumerate(STATUSES):
            target = self._catalogue_shares(status)
            q = [[self._rr(c, b) * max(target[c], 1e-300) for c in conds] for b in range(self.nb)]
            for _ in range(500):
                for b in range(self.nb):                       # rows sum to 1
                    t = sum(q[b])
                    q[b] = [x / t for x in q[b]]
                err = 0.0
                for ci, c in enumerate(conds):                 # columns match the catalogue's share
                    cur = sum(self.pop_b[si][b] * q[b][ci] for b in range(self.nb))
                    err = max(err, abs(cur - target[c]))
                    if cur > 0:
                        for b in range(self.nb):
                            q[b][ci] *= target[c] / cur
                if err < 1e-12:
                    break
            for b in range(self.nb):
                t = sum(q[b])
                q[b] = [x / t for x in q[b]]
            self.max_fit_error = max(self.max_fit_error, max(
                abs(sum(self.pop_b[si][b] * q[b][ci] for b in range(self.nb)) - target[c])
                for ci, c in enumerate(conds)))
            self.Q.append([dict(zip(conds, row)) for row in q])
        self.top = {c: max(self.Q[si][b][c] for si in range(3) for b in range(self.nb)) for c in conds}

    def condition_shares(self, bg: Mapping[str, Any]) -> dict[str, float]:
        """P(condition | smoking status, age band) for a background."""
        return self.Q[STATUSES.index(str(bg["smoking_status"]))][self.band(float(bg["age"]))]

    # ------------------------------------------------------------------ expectations (for the audit)
    def smoking_probs_given(self, age: float, sex: str, condition: str) -> list[float]:
        """P(smoking status | age, sex, primary condition)."""
        b = self.band(age)
        p = self.smoking_probs(age, sex)
        v = [p[i] * self.Q[i][b][condition] for i in range(3)]
        t = sum(v)
        return [x / t for x in v] if t > 0 else p

    def age_band_probs_given(self, status: str, sex: str, condition: str) -> list[float]:
        """P(age band | smoking status, sex, primary condition)."""
        si = STATUSES.index(status)
        v = [self.w[b] * self.p_smoke[sex][self._coarse(b)][si] * self.Q[si][b][condition] for b in range(self.nb)]
        t = sum(v)
        return [x / t for x in v] if t > 0 else [1.0 / self.nb] * self.nb

    def max_pack_years(self, age: float) -> float:
        """Most pack-years possible at ``age`` under the model's own limits (start no earlier than the minimum
        start age, at most ``max_packs_per_day``)."""
        lim = self.limits
        return float(lim.get("max_packs_per_day", 2.0)) * max(0.0, age - float(lim.get("min_start_age", 13)))

    # ------------------------------------------------------------------ drawing
    def draw_background(self, seed: int, index: int, k: int, fields: Mapping[str, Any]) -> dict[str, Any]:
        """Age, sex, smoking status, pack-years and region (those the catalogue has), drawn from keyed uniforms."""
        u = lambda name: uniform(seed, index, "bg", k, name)       # noqa: E731
        b = _pick(self.w, u("age"))
        lo, hi = self.edges[b], self.edges[b + 1]
        age = min(lo + int(u("age_within") * (hi - lo)), hi - 1)
        sex = self.sexes[_pick([self.sex_p[s] for s in self.sexes], u("sex"))]
        status = STATUSES[_pick(self.smoking_probs(age, sex), u("smoking_status"))]
        out: dict[str, Any] = {}
        if "age" in fields:
            out["age"] = age
        if "sex" in fields:
            out["sex"] = sex
        if "smoking_status" in fields:
            out["smoking_status"] = status
        if "pack_years" in fields:
            out["pack_years"] = self._pack_years(age, status, u, fields["pack_years"])
        if "region" in fields:
            keys = list(self.region_p)
            out["region"] = keys[_pick([self.region_p[r] for r in keys], u("region"))]
        return out

    def _pack_years(self, age: int, status: str, u, field) -> int:
        if status == "never":
            return 0
        sp = self.spec["pack_years"]
        st, q, pk = sp["start_age"], sp["years_since_quit"], sp["packs_per_day"]
        start = min(max(_lognormal(st["median"], st["log_sd"], u("start_age")), st["min"]), st["max"])
        start = min(start, age - 2.0)                   # at least 2 years of smoking at any age
        years = age - start
        if status == "former":
            years = max(1.0, years - _lognormal(q["median"], q["log_sd"], u("years_since_quit")))
        packs = min(max(_lognormal(pk["median"], pk["log_sd"], u("packs_per_day")), pk["min"]), pk["max"])
        hi = 200.0 if field.range[1] is None else field.range[1]
        return int(min(max(round(years * packs), 1), hi))


_CACHE: dict[tuple, PopulationModel | None] = {}


def get_model(catalogue) -> PopulationModel | None:
    """The population model for ``catalogue`` (``populations/<id>.yaml``), or ``None`` when that file does
    not exist or the catalogue lacks the fields it models (the skeleton then keeps its old default)."""
    path = population_path(catalogue.id)
    key = (catalogue.version_hash, str(path))
    if key in _CACHE:
        return _CACHE[key]
    model: PopulationModel | None = None
    if path.exists():
        try:
            spec = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError) as e:
            raise PopulationError(f"cannot read {path}: {e}") from None
        bg = catalogue.background
        ok = ("age" in bg and "smoking_status" in bg and "sex" in bg
              and tuple(bg["smoking_status"].values) == STATUSES
              and set(bg["sex"].values) == set(spec["sex"]))
        if spec.get("format") == "population/1" and ok:
            model = PopulationModel(spec, catalogue)
    _CACHE[key] = model
    return model
