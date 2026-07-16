"""SPEC-034/§6.12: model lineage manifest — exact field set, deterministic sha256 digest."""
from __future__ import annotations

import re

import pytest

from l1_reduce.reducer import environment_digest
from l4_pricing.manifest import ModelManifest

pytestmark = pytest.mark.spec("SPEC-034")


def _manifest(**overrides: object) -> ModelManifest:
    base: dict[str, object] = dict(
        model_id="stage-one-2026-07-16-a",
        training_data_manifest="TEST_ONLY:synthetic-fixture-v1",
        source_ids=("synthetic",),
        license_check_status="synthetic-no-licence-required",
        feature_schema_hash="f" * 64,
        code_commit="c" * 40,
        gate_results=(),
        approved_scope="offline-research",
    )
    base.update(overrides)
    return ModelManifest(**base)  # type: ignore[arg-type]


def test_carries_all_section_6_12_fields() -> None:
    m = _manifest()
    for field_name in (
        "model_id",
        "training_data_manifest",
        "source_ids",
        "license_check_status",
        "feature_schema_hash",
        "code_commit",
        "container_digest",
        "random_seeds",
        "gate_results",
        "approved_scope",
    ):
        assert hasattr(m, field_name)


def test_container_digest_reuses_the_platform_environment_digest() -> None:
    assert _manifest().container_digest == environment_digest()


def test_fits_are_deterministic_so_random_seeds_default_empty() -> None:
    assert _manifest().random_seeds == ()


def test_digest_is_deterministic_and_gate_compatible() -> None:
    a, b = _manifest(), _manifest()
    assert a.digest == b.digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", a.digest)


def test_digest_changes_with_any_field() -> None:
    base = _manifest().digest
    assert _manifest(model_id="other").digest != base
    assert _manifest(source_ids=("synthetic", "extra")).digest != base
    assert _manifest(approved_scope="different").digest != base
