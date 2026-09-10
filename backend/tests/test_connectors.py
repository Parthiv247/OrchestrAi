"""Connector Gallery endpoint smoke tests."""


def test_get_catalog_200(client):
    r = client.get("/api/connectors/catalog")
    assert r.status_code == 200
    body = r.json()
    # Response is {"catalog": {...}} keyed by category, not a flat list
    assert isinstance(body, dict)
    assert "catalog" in body or len(body) > 0


def test_get_catalog_entry_not_found(client):
    r = client.get("/api/connectors/catalog/nonexistent_connector_xyz")
    assert r.status_code == 404


def test_list_saved_connections_200(client):
    r = client.get("/api/connectors/saved")
    assert r.status_code == 200
    body = r.json()
    # Response is {"connections": [...]} — may include an "error" key when DB is down
    assert isinstance(body, dict)
    assert "connections" in body
    assert isinstance(body["connections"], list)


def test_test_connection_missing_body(client):
    r = client.post("/api/connectors/test", json={})
    assert r.status_code == 422


def test_test_connection_invalid_type(client):
    r = client.post("/api/connectors/test", json={"connector_type": "nonexistent_db", "config": {}})
    # Either 400 (unknown type) or 200 with error flag
    assert r.status_code in (200, 400)


def test_create_saved_connection_missing_fields(client):
    r = client.post("/api/connectors/saved", json={"name": "test"})
    assert r.status_code == 422


def test_get_source_connectors_200(client):
    r = client.get("/api/connectors/sources")
    assert r.status_code == 200


def test_get_destination_connectors_200(client):
    r = client.get("/api/connectors/destinations")
    assert r.status_code == 200
