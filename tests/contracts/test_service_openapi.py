"""Service OpenAPI shape: the routes the web app and the docs rely on exist, and those with response models keep them.

Routes without a response model today (runs, datasets, models, optimisations) are listed in NO_SCHEMA_YET so adding
one is fine, and so is removing it from the list; a route silently losing its model or disappearing is what fails."""

import pytest

from service.app import create_app
from service.config import Settings


@pytest.fixture(scope="module")
def spec(tmp_path_factory):
    d = tmp_path_factory.mktemp("openapi")
    return create_app(Settings(data_dir=d / "data", web_dir=d / "noweb")).openapi()


# (method, path) pairs whose success response documents a JSON schema
WITH_SCHEMA = [
    ("get", "/api/access"), ("post", "/api/projects/{p}/decide"),
    ("get", "/api/projects"), ("post", "/api/projects"), ("get", "/api/projects/{p}"), ("patch", "/api/projects/{p}"),
    ("get", "/api/projects/{p}/world"), ("put", "/api/projects/{p}/world"),
    ("get", "/api/projects/{p}/flowcharts"), ("post", "/api/projects/{p}/flowcharts"), ("get", "/api/projects/{p}/flowcharts/{f}"),
    ("get", "/api/projects/{p}/flowcharts/{f}/versions"), ("post", "/api/projects/{p}/flowcharts/{f}/versions"),
    ("get", "/api/projects/{p}/flowcharts/{f}/versions/{v}"), ("put", "/api/projects/{p}/flowcharts/{f}/versions/{v}"),
    ("post", "/api/projects/{p}/validate"), ("get", "/api/templates"), ("get", "/api/templates/{template_id}"),
]
# routes that must exist (the web app and docs/platform call them); schema not required yet
NO_SCHEMA_YET = [
    ("get", "/api/health"), ("post", "/api/projects/{p}/runs"), ("get", "/api/projects/{p}/runs/{r}"),
    ("get", "/api/projects/{p}/runs/{r}/bundle"), ("get", "/api/projects/{p}/runs/{r}/flow"),
    ("get", "/api/projects/{p}/runs/{r}/decisions"), ("post", "/api/projects/{p}/compare"),
    ("post", "/api/projects/{p}/optimisations"), ("get", "/api/projects/{p}/optimisations/{o}"),
    ("post", "/api/projects/{p}/optimisations/{o}/apply"), ("get", "/api/jobs/{j}"),
]


def success(op):
    return [r for c, r in op["responses"].items() if c.startswith("2")]


def test_info_and_prefix(spec):
    assert spec["info"]["title"] and spec["info"]["version"]
    assert all(p.startswith("/api/") for p in spec["paths"])


@pytest.mark.parametrize("method,path", WITH_SCHEMA)
def test_documented_route_keeps_its_response_model(spec, method, path):
    op = spec["paths"][path][method]
    assert any("application/json" in r.get("content", {}) and r["content"]["application/json"].get("schema") for r in success(op)), (method, path)


@pytest.mark.parametrize("method,path", NO_SCHEMA_YET)
def test_route_exists(spec, method, path):
    assert method in spec["paths"][path]
    assert success(spec["paths"][path][method])


def test_response_schemas_resolve(spec):
    comps = spec["components"]["schemas"]
    for path in spec["paths"].values():
        for op in path.values():
            for r in success(op):
                ref = r.get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
                if ref:
                    assert ref.rsplit("/", 1)[-1] in comps, ref
