"""OpenAPI documentation tests."""

from api.app import app


def test_search_openapi_schema_describes_the_request_flow() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/search"]["post"]
    request_properties = schema["components"]["schemas"]["SearchRequest"]["properties"]
    timing_properties = schema["components"]["schemas"]["SearchTimings"]["properties"]

    assert (
        operation["summary"]
        == "Search, optionally crawl and rank, then clean documents"
    )
    assert operation["tags"] == ["Search"]
    assert "Fetch candidate URLs" in request_properties["crawl_websites"]["description"]
    assert (
        "target_documents"
        in request_properties["rank_and_score_deterministically"]["description"]
    )
    assert timing_properties["compression_latency_ms"]["description"]
    assert {"200", "422", "429"} <= set(operation["responses"])
