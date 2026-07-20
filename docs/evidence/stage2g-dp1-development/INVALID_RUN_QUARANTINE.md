INVALID_COMPARATOR_CONFIGURATION (founder pre-result control §1, 2026-07-20)
Run: dp1_run.py stage2g-dp1-run-v1, killed mid-execution after the founder-directed
comparator audit found FROZEN_F2_K=24.0 applied to BOTH tours, while the frozen
F2-v1 selection is ATP K=24.0 / WTA K=32.0 (F2_EVALUATION_REPORT.json selected_k;
selection rule per f2-global-elo-registration-v1.yaml k_selection).
The single artifact written (DP1G2_EVALUATION_REPORT_ATP.json) is preserved as an
OPERATIONAL artifact only — it is NOT evidence, and its numerical contents were
never displayed, read, or summarized in the operating session (the run's stdout
reached the session as 0 bytes; verified). WTA and manifest were never written.

quarantined_artifact_sha256: bdba2b573679563005391929fb61a22ff9af13cc13ceef9d8442af87848f06f6
artifact: DP1G2_EVALUATION_REPORT_ATP.json (scratchpad quarantine-invalid-comparator/; operational only)
stdout_bytes_reaching_session: 0 (verified via the task output file byte count)
wta_report: never written; manifest: never written
