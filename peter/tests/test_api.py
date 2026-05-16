"""HTTP API tests (Starlette TestClient; no TLS)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from starlette.testclient import TestClient

from irpete.app import create_app
from irpete.config import Settings

from irpete.validate import LEADING_GAP_US, MAX_RAW_ELEMENTS


def auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _sample_envelope(label: str = "tv_power") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "label": label,
        "carrier_hz": 38000,
        "raw_us": [1000, 500, 1000, 500],
    }


def test_health_missing_auth(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 401


def test_openapi_routes_hidden_when_disabled(settings: Settings, api_key: str) -> None:
    s = replace(settings, disable_openapi=True)
    with TestClient(create_app(s)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert (
            client.get("/v1/health", headers=auth(api_key)).status_code == 200
        )


def test_health_wrong_key(client: TestClient, api_key: str) -> None:
    r = client.get(
        "/v1/health",
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_health_wrong_scheme_401(client: TestClient) -> None:
    r = client.get("/v1/health", headers={"Authorization": "Basic dGVzdA=="})
    assert r.status_code == 401


def test_health_ok(client: TestClient, api_key: str) -> None:
    r = client.get("/v1/health", headers=auth(api_key))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_post_get_roundtrip(client: TestClient, api_key: str) -> None:
    body = _sample_envelope()
    p = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert p.status_code == 200
    posted = p.json()
    assert posted["carrier_hz"] == 38000
    assert posted["raw_us"] == body["raw_us"]

    g = client.get("/v1/signals/tv_power", headers=auth(api_key))
    assert g.status_code == 200
    assert g.json() == posted


def test_get_unknown_label_404(client: TestClient, api_key: str) -> None:
    r = client.get("/v1/signals/nope", headers=auth(api_key))
    assert r.status_code == 404


def test_invalid_envelope_422(client: TestClient, api_key: str) -> None:
    bad = _sample_envelope()
    bad["carrier_hz"] = 10_000
    r = client.post("/v1/signals", json=bad, headers=auth(api_key))
    assert r.status_code == 422


def test_list_signals_no_raw_us(client: TestClient, api_key: str) -> None:
    client.post(
        "/v1/signals",
        json=_sample_envelope("btn_a"),
        headers=auth(api_key),
    )
    r = client.get("/v1/signals", headers=auth(api_key))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["label"] == "btn_a")
    assert "raw_us" not in item
    assert item["carrier_hz"] == 38000
    assert "updated_at" in item


def test_upsert_by_label(client: TestClient, api_key: str) -> None:
    first = _sample_envelope("same")
    client.post("/v1/signals", json=first, headers=auth(api_key))
    second = dict(first)
    second["raw_us"] = [2000, 1000, 2000, 1000]
    r = client.post("/v1/signals", json=second, headers=auth(api_key))
    assert r.status_code == 200
    assert r.json()["raw_us"] == second["raw_us"]

    g = client.get("/v1/signals/same", headers=auth(api_key))
    assert g.json()["raw_us"] == second["raw_us"]


def test_list_pagination_total(client: TestClient, api_key: str) -> None:
    for i in range(3):
        client.post(
            "/v1/signals",
            json=_sample_envelope(f"pag_{i}"),
            headers=auth(api_key),
        )
    r = client.get(
        "/v1/signals",
        params={"limit": 2, "offset": 0},
        headers=auth(api_key),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_post_normalizes_leading_gap(client: TestClient, api_key: str) -> None:
    body = {
        "schema_version": 1,
        "label": "norm_test",
        "carrier_hz": 38000,
        "raw_us": [LEADING_GAP_US + 1, 1000, 500, 1000, 500],
    }
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 200
    assert r.json()["raw_us"] == [1000, 500, 1000, 500]


def test_all_v1_routes_require_auth(client: TestClient) -> None:
    body = _sample_envelope("need_auth")
    assert client.post("/v1/signals", json=body).status_code == 401
    assert client.get("/v1/signals").status_code == 401
    assert client.get("/v1/signals/any").status_code == 401


def test_401_includes_www_authenticate(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("bearer")


def test_post_optional_fields_roundtrip(client: TestClient, api_key: str) -> None:
    body = _sample_envelope("with_opts")
    body["repeat"] = 2
    body["notes"] = "living room TV"
    assert (
        client.post("/v1/signals", json=body, headers=auth(api_key)).status_code
        == 200
    )
    r = client.get("/v1/signals/with_opts", headers=auth(api_key))
    assert r.status_code == 200
    data = r.json()
    assert data["repeat"] == 2
    assert data["notes"] == "living room TV"


def test_get_unknown_includes_detail(client: TestClient, api_key: str) -> None:
    r = client.get("/v1/signals/missing_label", headers=auth(api_key))
    assert r.status_code == 404
    assert "Unknown label" in r.json()["detail"]


def test_post_extra_field_422(client: TestClient, api_key: str) -> None:
    body = _sample_envelope()
    body["foo"] = "bar"
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 422


def test_post_schema_version_unsupported_422(client: TestClient, api_key: str) -> None:
    body = _sample_envelope()
    body["schema_version"] = 99
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 422


def test_post_raw_us_too_long_422(client: TestClient, api_key: str) -> None:
    raw_us = [1000, 500] * (MAX_RAW_ELEMENTS // 2) + [1000]
    assert len(raw_us) == MAX_RAW_ELEMENTS + 1
    body = _sample_envelope("too_long")
    body["raw_us"] = raw_us
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 422


def test_post_missing_required_field_422(client: TestClient, api_key: str) -> None:
    body = _sample_envelope()
    del body["carrier_hz"]
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 422


def test_list_query_limit_zero_422(client: TestClient, api_key: str) -> None:
    r = client.get(
        "/v1/signals", params={"limit": 0}, headers=auth(api_key)
    )
    assert r.status_code == 422


def test_list_query_limit_over_max_422(client: TestClient, api_key: str) -> None:
    r = client.get(
        "/v1/signals", params={"limit": 501}, headers=auth(api_key)
    )
    assert r.status_code == 422


def test_list_query_negative_offset_422(client: TestClient, api_key: str) -> None:
    r = client.get(
        "/v1/signals", params={"offset": -1}, headers=auth(api_key)
    )
    assert r.status_code == 422


def test_list_offset_second_row(client: TestClient, api_key: str) -> None:
    for lab in ["lbl_z", "lbl_a", "lbl_m"]:
        client.post(
            "/v1/signals",
            json=_sample_envelope(lab),
            headers=auth(api_key),
        )
    r = client.get(
        "/v1/signals",
        params={"limit": 1, "offset": 1},
        headers=auth(api_key),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["label"] == "lbl_m"


def test_post_pulse_above_uint16_422(client: TestClient, api_key: str) -> None:
    body = _sample_envelope("big_pulse")
    body["raw_us"] = [1000, 70000, 1000, 500]
    r = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert r.status_code == 422


def test_post_get_full_envelope_semantics(client: TestClient, api_key: str) -> None:
    """Same carrier + raw + schema_version after POST and GET (Stage 1 verification)."""
    body = {
        "schema_version": 1,
        "label": "semantic_check",
        "carrier_hz": 40000,
        "raw_us": [1200, 600, 900, 450],
    }
    p = client.post("/v1/signals", json=body, headers=auth(api_key))
    assert p.status_code == 200
    posted = p.json()
    g = client.get("/v1/signals/semantic_check", headers=auth(api_key))
    assert g.status_code == 200
    got = g.json()
    for k in ("schema_version", "label", "carrier_hz", "raw_us"):
        assert got[k] == posted[k] == body[k]
