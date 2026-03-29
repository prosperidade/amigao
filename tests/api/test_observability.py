def test_metrics_endpoint_exposes_http_metrics(client):
    health_response = client.get("/health")
    assert health_response.status_code == 200

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "amigao_http_requests_total" in metrics_response.text
    assert "amigao_http_request_duration_seconds" in metrics_response.text
