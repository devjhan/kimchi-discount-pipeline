"""Generate ``governance/policy/methods_manifest.yaml`` from the code SSoT (ADR-0014).

The cutoff/selector vocabulary lives in code (screener ``RuleFactory`` / ``resolver`` /
``leaf`` + segment_registry ``attributes``). This script projects that code-owned
vocabulary into a single declarative manifest that:

- the ``policy-profiler`` skill references as its metric_path / type / op whitelist
  (SoT #5) — so the SOP no longer points at a non-existent file;
- the policy strict cutoff validator reads as DATA (bc-independent — policy never imports
  screener internals);
- the repo-wide policy-contract arch test conforms on-disk profiles against.

GENERATED ARTIFACT — do not hand-edit. ``test_methods_manifest_sync`` fails the build if
the on-disk file drifts from the code (regenerate: ``python -m applications.gen_methods_manifest``).
"""
from __future__ import annotations

import sys
from typing import Any

import yaml

from domains._shared.segment_registry.attributes import (
    CATEGORICAL_OPS,
    NUMERIC_OPS,
    SELECTION_ATTRIBUTES,
)
from domains.screener.rules.factory import RULE_TYPES
from domains.screener.rules.leaf import THRESHOLD_OPS
from domains.screener.rules.resolver import (
    _ENRICHMENT_PREFIX,
    _ENRICHMENT_WHITELIST,
    _REGISTRY,
)
from infrastructure._common import utils

SCHEMA_VERSION = "methods-manifest-v1"


def build_manifest() -> dict[str, Any]:
    """Project the code-owned cutoff/selector vocabulary into a manifest dict.

    Pure (no I/O). Both the CLI dump and the sync arch test call this — identical source.
    """
    enrichment_paths = sorted(
        f"{_ENRICHMENT_PREFIX}{group}.{key}" for group, key in _ENRICHMENT_WHITELIST
    )
    return {
        "schema": SCHEMA_VERSION,
        "description": (
            "GENERATED from code SSoT (screener rules + segment_registry attributes). "
            "Do not hand-edit — regenerate via 'python -m applications.gen_methods_manifest'. "
            "cutoff_rules metric_path/op/type 화이트리스트 (ADR-0014)."
        ),
        "metric_paths": sorted(_REGISTRY.keys()),
        "enrichment_metric_paths": enrichment_paths,
        "rule_types": sorted(RULE_TYPES),
        "threshold_ops": sorted(THRESHOLD_OPS),
        "selection_attributes": dict(sorted(SELECTION_ATTRIBUTES.items())),
        "selector_ops": {
            "numeric": sorted(NUMERIC_OPS),
            "categorical": sorted(CATEGORICAL_OPS),
        },
    }


def manifest_yaml() -> str:
    """Deterministic YAML serialization of the manifest (sorted keys, unicode preserved)."""
    return yaml.safe_dump(build_manifest(), sort_keys=True, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    out_path = utils.policy_root_dir() / "methods_manifest.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(manifest_yaml(), encoding="utf-8")
    print(f"[gen_methods_manifest] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

