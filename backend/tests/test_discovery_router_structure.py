from app.main import app


def test_discovery_search_routes_are_registered():
    registered = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("POST", "/api/v1/projects/{project_id}/discovery/search") in registered
    assert ("GET", "/api/v1/projects/{project_id}/discovery/executions/{execution_id}") in registered
    assert ("POST", "/api/v1/projects/{project_id}/discovery/favorites") in registered
    assert ("GET", "/api/v1/projects/{project_id}/discovery/favorites") in registered
    assert ("DELETE", "/api/v1/projects/{project_id}/discovery/favorites/{favorite_id}") in registered
    assert ("POST", "/api/v1/projects/{project_id}/discovery/import") in registered


def test_discovery_openapi_contract_exposes_typed_request_and_response():
    paths = app.openapi()["paths"]
    search = paths["/api/v1/projects/{project_id}/discovery/search"]["post"]
    execution = paths["/api/v1/projects/{project_id}/discovery/executions/{execution_id}"]["get"]

    assert search["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiscoverySearchRequest"
    )
    assert search["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/LiteratureSearchResponse"
    )
    execution_schema = execution["responses"]["200"]["content"]["application/json"]["schema"]
    assert execution_schema["type"] == "object"


def test_favorite_and_import_openapi_contracts_are_typed():
    paths = app.openapi()["paths"]
    favorites = paths["/api/v1/projects/{project_id}/discovery/favorites"]["post"]
    importer = paths["/api/v1/projects/{project_id}/discovery/import"]["post"]

    assert favorites["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiscoveryFavoriteRequest"
    )
    assert favorites["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiscoveryFavoriteResponse"
    )
    assert importer["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiscoveryImportRequest"
    )
    assert importer["responses"]["202"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiscoveryImportResponse"
    )
