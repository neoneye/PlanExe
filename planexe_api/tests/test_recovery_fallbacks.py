"""Regression tests for recovery workspace fallbacks."""

import asyncio
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import types


def _bootstrap_api(tmp_path: Path, fallback_enabled: bool = True):
    """Reload the FastAPI app against an isolated SQLite database."""

    db_path = tmp_path / "planexe.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["PLANEXE_ENABLE_AGENT_FALLBACK"] = "true" if fallback_enabled else "false"
    os.environ["PLANEXE_CLOUD_MODE"] = "true"

    if "sse_starlette" not in sys.modules:
        sse_stub = types.ModuleType("sse_starlette")

        class _EventSourceResponse:  # pragma: no cover - stub for import satisfaction
            def __init__(self, *args, **kwargs):
                raise RuntimeError("EventSourceResponse is not available in test mode")

        sse_stub.EventSourceResponse = _EventSourceResponse
        sys.modules["sse_starlette"] = sse_stub

    for module_name in [
        "planexe_api.api",
        "planexe_api.database",
        "planexe_api.services.pipeline_execution_service",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]

    import planexe_api.database as database_module  # type: ignore
    import planexe_api.api as api_module  # type: ignore

    return api_module, database_module


def test_plan_details_falls_back_to_database_log(tmp_path):
    api_module, database_module = _bootstrap_api(tmp_path)

    client = TestClient(api_module.app)
    db_service = database_module.get_database_service()

    plan_id = "plan-log-fallback"
    output_dir = tmp_path / "missing" / plan_id

    db_service.create_plan(
        {
            "plan_id": plan_id,
            "prompt": "test prompt",
            "llm_model": "test-llm",
            "speed_vs_detail": "ALL_DETAILS_BUT_SLOW",
            "status": "completed",
            "progress_percentage": 100,
            "progress_message": "done",
            "output_dir": str(output_dir),
        }
    )

    log_text = "log line from database"
    db_service.create_plan_content(
        {
            "plan_id": plan_id,
            "filename": "log.txt",
            "stage": "pipeline",
            "content_type": "txt",
            "content": log_text,
            "content_size_bytes": len(log_text.encode("utf-8")),
        }
    )
    db_service.close()

    response = client.get(f"/api/plans/{plan_id}/details")
    assert response.status_code == 200
    assert response.json()["pipeline_log"] == log_text


def test_file_download_endpoint_uses_database_when_missing(tmp_path):
    api_module, database_module = _bootstrap_api(tmp_path)

    client = TestClient(api_module.app)
    db_service = database_module.get_database_service()

    plan_id = "plan-file-fallback"
    output_dir = tmp_path / "missing" / plan_id

    db_service.create_plan(
        {
            "plan_id": plan_id,
            "prompt": "download test",
            "llm_model": "test-llm",
            "speed_vs_detail": "ALL_DETAILS_BUT_SLOW",
            "status": "completed",
            "progress_percentage": 100,
            "progress_message": "done",
            "output_dir": str(output_dir),
        }
    )

    json_payload = "{\n  \"ok\": true\n}"
    db_service.create_plan_content(
        {
            "plan_id": plan_id,
            "filename": "001-output.json",
            "stage": "stage_one",
            "content_type": "json",
            "content": json_payload,
            "content_size_bytes": len(json_payload.encode("utf-8")),
        }
    )
    db_service.close()

    response = client.get(f"/api/plans/{plan_id}/files/001-output.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.text == json_payload


def test_failed_pipeline_persists_log_into_database(tmp_path):
    api_module, database_module = _bootstrap_api(tmp_path, fallback_enabled=False)

    db_service = database_module.get_database_service()

    plan_id = "plan-failure-log"
    run_dir = tmp_path / "run" / plan_id
    run_dir.mkdir(parents=True)

    log_text = "failure diagnostics"
    (run_dir / "log.txt").write_text(log_text, encoding="utf-8")

    db_service.create_plan(
        {
            "plan_id": plan_id,
            "prompt": "failure test",
            "llm_model": "test-llm",
            "speed_vs_detail": "ALL_DETAILS_BUT_SLOW",
            "status": "running",
            "progress_percentage": 10,
            "progress_message": "running",
            "output_dir": str(run_dir),
        }
    )

    asyncio.run(api_module.pipeline_service._finalize_plan_status(plan_id, 1, run_dir, db_service))

    stored_log = db_service.get_plan_content_by_filename(plan_id, "log.txt")
    assert stored_log is not None
    assert stored_log.content == log_text

    db_service.close()
