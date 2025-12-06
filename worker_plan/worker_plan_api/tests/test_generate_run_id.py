from datetime import datetime

from worker_plan_api.generate_run_id import RUN_ID_PREFIX, generate_run_id


def test_generate_run_id_timestamp():
    start_time = datetime(2024, 1, 2, 3, 4, 5)
    run_id = generate_run_id(use_uuid=False, start_time=start_time)
    assert run_id.startswith(RUN_ID_PREFIX)
    assert run_id == f"{RUN_ID_PREFIX}20240102_030405"


def test_generate_run_id_uuid():
    start_time = datetime(2024, 1, 2, 3, 4, 5)
    run_id = generate_run_id(use_uuid=True, start_time=start_time)
    assert run_id.startswith(RUN_ID_PREFIX)
    # UUID part should not be empty and should contain hyphens.
    uuid_part = run_id[len(RUN_ID_PREFIX):]
    assert len(uuid_part) > 0
    assert "-" in uuid_part
