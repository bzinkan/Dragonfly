from datetime import UTC, datetime

from app.ingest.contracts import (
    IngestEnvelope,
    IngestResult,
    IngestSource,
    IngestStatus,
    ObservationIngestPayload,
)
from app.ingest.runs import mark_failed, mark_succeeded


def test_ingest_envelope_accepts_observation_payload() -> None:
    payload = ObservationIngestPayload(
        kind="observation_submitted",
        observation_id="01HOBSERVATION000000000000",
        user_id="01HUSER000000000000000000",
        group_id="01HGROUP00000000000000000",
        photo_id="01HPHOTO0000000000000000",
        taxon_id=47157,
    )

    envelope = IngestEnvelope(
        source=IngestSource.OBSERVATION,
        source_run_id=payload.observation_id,
        payload=payload.model_dump(),
        occurred_at=datetime.now(tz=UTC),
    )

    assert envelope.source == IngestSource.OBSERVATION
    assert envelope.source_run_id == payload.observation_id


def test_ingest_result_transitions_are_immutable() -> None:
    result = IngestResult(
        source=IngestSource.EXPEDITION_CONTENT,
        source_run_id="content-hash",
        status=IngestStatus.RUNNING,
        processed_count=1,
        skipped_count=0,
        retry_count=0,
    )

    succeeded = mark_succeeded(result)
    failed = mark_failed(result, "x" * 3000)

    assert result.status == IngestStatus.RUNNING
    assert succeeded.status == IngestStatus.SUCCEEDED
    assert failed.status == IngestStatus.FAILED
    assert failed.retry_count == 1
    assert failed.last_error is not None
    assert len(failed.last_error) == 2000
