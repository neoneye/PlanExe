/**
 * Author: Codex using GPT-5
 * Date: 2025-10-16T00:00:00Z
 * PURPOSE: Document alignment of canonical report filename between Luigi output and FastAPI endpoints for Railway deployment stability.
 * SRP and DRY check: Pass - Focused deployment note; cross-checked existing docs to avoid duplication.
 */

# 2025-10-16 – Canonical Report Endpoint Repair

## Summary
- FastAPI now references `FilenameEnum.REPORT` (`029-report.html`) for `has_report` detection and report downloads.
- Minimal fallback generator persists the same filename and marks the artefact as part of the `reporting` stage.
- Resolves production 404s when recovery workspace tries to fetch `/api/plans/{plan_id}/report`.

## Validation Checklist
- [x] Triggered fallback path in code to ensure `reporting` stage metadata is stored alongside HTML payload.
- [x] Confirmed `FilenameEnum.REPORT.value` is shared by Luigi pipeline outputs.
- [ ] (Pending Railway redeploy) Verify canonical report download succeeds post-deployment.

## Follow-ups
- Monitor production logs for lingering 404s after redeployment.
- Consider surfacing fallback HTML inline when canonical report missing to reduce user confusion.
