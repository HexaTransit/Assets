#!/usr/bin/env python3
"""Validate trafic.json files under `logo/` against the JSON Schema in `.github/models/trafic.schema.json`.

Usage:
  python .github/scripts/check_structure_trafic.py [--schema PATH] [--logo-dir PATH]

Exits with code 0 when all files are valid, otherwise exits with 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

try:
    import jsonschema
    from jsonschema import Draft7Validator, FormatChecker
except Exception:  # pragma: no cover - helpful message when module missing
    print("ERROR: the 'jsonschema' package is required. Install with: pip install jsonschema", file=sys.stderr)
    raise


def find_trafic_files(root: Path) -> List[Path]:
    """Return list of paths named 'trafic.json' under root/logo (recursively)."""
    logo_dir = root / "logo"
    if not logo_dir.exists():
        return []
    return list(logo_dir.rglob("trafic.json"))


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_instance(schema: dict, instance: dict, instance_path: Path) -> List[str]:
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: e.path):
        # build a readable location
        location = "".join(f"/{p}" for p in err.absolute_path) or "/"
        errors.append(f"{instance_path}: {location} -> {err.message}")
    return errors


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_structure_trafic.py", description="Validate trafic.json files against JSON Schema")
    parser.add_argument("--schema", "-s", type=Path, default=Path(__file__).resolve().parents[2] / ".github" / "models" / "trafic.schema.json", help="Path to trafic.schema.json")
    parser.add_argument("--root", "-r", type=Path, default=Path(__file__).resolve().parents[2], help="Repository root (default: repo root)")
    parser.add_argument("--logo-dir", type=Path, help="Optional explicit logo directory (overrides --root/logo)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only print errors and exit code")
    args = parser.parse_args(argv)

    schema_path = args.schema
    repo_root = args.root
    if args.logo_dir:
        logo_root = args.logo_dir
    else:
        logo_root = repo_root / "logo"

    if not schema_path.exists():
        print(f"ERROR: schema file not found at {schema_path}", file=sys.stderr)
        return 2

    try:
        schema = load_json(schema_path)
    except Exception as exc:
        print(f"ERROR: failed to load schema {schema_path}: {exc}", file=sys.stderr)
        return 2

    files = find_trafic_files(repo_root) if not args.logo_dir else list(Path(args.logo_dir).rglob("trafic.json"))
    if not files:
        print(f"No trafic.json files found under {logo_root}")
        return 0

    total = 0
    invalid = 0
    all_errors: List[str] = []

    for f in sorted(files):
        total += 1
        try:
            instance = load_json(f)
        except Exception as exc:
            invalid += 1
            all_errors.append(f"{f}: JSON parse error: {exc}")
            continue

        errors = validate_instance(schema, instance, f)
        if errors:
            invalid += 1
            all_errors.extend(errors)
        else:
            if not args.quiet:
                print(f"OK: {f}")

    if all_errors:
        print("\nValidation errors:")
        for e in all_errors:
            print(" -", e)

    print(f"\nChecked {total} files: {total - invalid} valid, {invalid} invalid")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
