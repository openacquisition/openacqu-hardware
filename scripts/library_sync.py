#!/usr/bin/env python3
"""Point every KiCad project at the shared library with project-relative paths.

Finds each directory that contains a .kicad_pro and rewrites:

- sym-lib-table, one row per file in library/openacqu_symbols
- fp-lib-table, one row for the library/openacqu_footprints directory
- (model "...") paths in footprints that point at library/openacqu_step,
  using ${KIPRJMOD} and the same relative prefix from every project

Schematics, boards, and symbol files are left unchanged. Footprint fields
and STEP links that do not already point at a file in the shared library
are reported and not guessed.

Run from anywhere:

    python scripts/library_sync.py
    python scripts/library_sync.py --check
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = REPO_ROOT / "library"
SYMBOL_DIR = LIBRARY_DIR / "openacqu_symbols"
FOOTPRINT_DIR = LIBRARY_DIR / "openacqu_footprints"
STEP_DIR = LIBRARY_DIR / "openacqu_step"
FOOTPRINT_LIB_NAME = "openacqu_footprints"
STEP_MARKER = "library/openacqu_step/"
MODEL_RE = re.compile(r'(\(model\s+")([^"]*)(")')


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def kicad_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def kicad_uri(project_dir: Path, target: Path) -> str:
    relative = Path(os.path.relpath(target, project_dir)).as_posix()
    return "${KIPRJMOD}/" + relative


def find_projects(root: Path) -> list[Path]:
    projects: list[Path] = []
    for project_file in sorted(root.rglob("*.kicad_pro")):
        parts = project_file.relative_to(root).parts
        if any(part.startswith(".") for part in parts):
            continue
        projects.append(project_file.parent)
    return projects


def parse_sexpr(text: str):
    """Parse one KiCad s-expression into nested lists and atoms."""
    length = len(text)
    index = 0

    def skip_ws() -> None:
        nonlocal index
        while index < length and text[index] in " \t\r\n":
            index += 1

    def parse_value():
        nonlocal index
        skip_ws()
        if index >= length:
            raise ValueError("unexpected end of file")
        if text[index] == "(":
            index += 1
            items = []
            while True:
                skip_ws()
                if index >= length:
                    raise ValueError("unclosed list")
                if text[index] == ")":
                    index += 1
                    return items
                items.append(parse_value())
        if text[index] == '"':
            index += 1
            chars: list[str] = []
            while index < length:
                char = text[index]
                if char == "\\":
                    index += 1
                    if index >= length:
                        raise ValueError("truncated escape")
                    chars.append(text[index])
                    index += 1
                    continue
                if char == '"':
                    index += 1
                    return "".join(chars)
                chars.append(char)
                index += 1
            raise ValueError("unclosed string")
        start = index
        while index < length and text[index] not in " \t\r\n()":
            index += 1
        if start == index:
            raise ValueError(f"bad token at character {index}")
        return text[start:index]

    skip_ws()
    return parse_value()


def list_head(node) -> str | None:
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return None


def read_symbols(path: Path) -> tuple[list[tuple[str, str | None]], str | None]:
    """Return (symbol name, footprint field) for each top-level symbol."""
    try:
        root = parse_sexpr(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [], str(exc)
    if list_head(root) != "kicad_symbol_lib":
        return [], "file is not a kicad_symbol_lib"
    found: list[tuple[str, str | None]] = []
    for child in root[1:]:
        if list_head(child) != "symbol" or len(child) < 2 or not isinstance(child[1], str):
            continue
        footprint = None
        for item in child[2:]:
            if (
                list_head(item) == "property"
                and len(item) >= 3
                and item[1] == "Footprint"
                and isinstance(item[2], str)
            ):
                footprint = item[2]
                break
        found.append((child[1], footprint))
    return found, None


def render_lib_table(root_name: str, rows: list[tuple[str, str]]) -> str:
    lines = [f"({root_name}", "\t(version 7)"]
    for name, uri in rows:
        lines.append(
            f"\t(lib (name {kicad_quote(name)}) (type \"KiCad\") "
            f"(uri {kicad_quote(uri)}) (options \"\") (descr \"\"))"
        )
    lines.append(")")
    return "\n".join(lines) + "\n"


def step_filename(model_path: str) -> str | None:
    """Return the STEP basename when the path points at the shared step directory."""
    normalized = model_path.replace("\\", "/")
    marker_at = normalized.lower().rfind(STEP_MARKER)
    if marker_at != -1:
        remainder = normalized[marker_at + len(STEP_MARKER) :]
        if remainder and "/" not in remainder:
            return remainder
        return None
    candidate = Path(model_path)
    if candidate.is_absolute():
        try:
            if candidate.parent.resolve() == STEP_DIR.resolve():
                return candidate.name
        except OSError:
            return None
    return None


def files_by_lower(directory: Path, suffix: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == suffix:
            found[path.name.lower()] = path.name
    return found


def discover_step_files() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in STEP_DIR.iterdir():
        if path.is_file():
            found[path.name.lower()] = path.name
    return found


class SyncPlan:
    def __init__(self) -> None:
        self.notes: list[str] = []
        self.warnings: list[str] = []
        self.writes: list[tuple[Path, str]] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def plan_symbols(plan: SyncPlan, footprint_files: dict[str, str]) -> list[str]:
    symbol_files = sorted(
        path for path in SYMBOL_DIR.iterdir() if path.is_file() and path.suffix == ".kicad_sym"
    )
    nicknames: list[str] = []
    for path in symbol_files:
        nicknames.append(path.stem)
        symbols, error = read_symbols(path)
        display = repo_rel(path)
        if error:
            plan.warn(f"{display}: could not read symbols ({error})")
            continue
        if len(symbols) != 1:
            names = ", ".join(name for name, _ in symbols) or "(none)"
            plan.warn(f"{display}: expected one symbol, found {len(symbols)} ({names})")
        for name, footprint in symbols:
            if name != path.stem:
                plan.warn(
                    f"{display}: symbol name {name!r} does not match the filename"
                )
            if footprint is None or footprint == "":
                plan.warn(f"{display}: symbol {name!r} has no Footprint field")
                continue
            if ":" in footprint:
                library, footprint_name = footprint.split(":", 1)
            else:
                library, footprint_name = "", footprint
            problems: list[str] = []
            if library != FOOTPRINT_LIB_NAME:
                if library == "":
                    problems.append("has no library nickname")
                else:
                    problems.append(f"uses library {library!r}")
            expected = footprint_name + ".kicad_mod"
            if expected.lower() not in footprint_files:
                problems.append(
                    f"has no file {repo_rel(FOOTPRINT_DIR / expected)}"
                )
            if problems:
                detail = "; ".join(problems)
                plan.warn(f"{display}: Footprint {footprint!r} {detail}")
    return nicknames


def plan_models(plan: SyncPlan, step_prefix: str, step_files: dict[str, str]) -> set[str]:
    referenced: set[str] = set()
    footprint_paths = sorted(
        path for path in FOOTPRINT_DIR.iterdir() if path.is_file() and path.suffix == ".kicad_mod"
    )
    for path in footprint_paths:
        original = path.read_bytes().decode("utf-8")
        matches = list(MODEL_RE.finditer(original))
        if not matches:
            plan.warn(f"{repo_rel(path)}: no 3D model")
            continue
        changed = False

        def replace(match: re.Match[str], path: Path = path) -> str:
            nonlocal changed
            model_path = match.group(2)
            filename = step_filename(model_path)
            if filename is None:
                plan.warn(
                    f"{repo_rel(path)}: 3D model is outside {STEP_MARKER} ({model_path})"
                )
                return match.group(0)
            actual = step_files.get(filename.lower())
            if actual is None:
                plan.warn(
                    f"{repo_rel(path)}: 3D model {filename!r} is not in {repo_rel(STEP_DIR)}"
                )
                return match.group(0)
            referenced.add(actual)
            new_path = "${KIPRJMOD}/" + step_prefix + "/" + actual
            if new_path == model_path:
                return match.group(0)
            changed = True
            return match.group(1) + new_path + match.group(3)

        updated = MODEL_RE.sub(replace, original)
        if changed:
            plan.writes.append((path, updated))

    for actual in sorted(step_files.values(), key=str.lower):
        if actual not in referenced:
            plan.warn(f"{repo_rel(STEP_DIR / actual)}: not referenced by any footprint")
    return referenced


def plan_tables(plan: SyncPlan, projects: list[Path], nicknames: list[str]) -> None:
    for project_dir in projects:
        symbol_rows = [
            (name, kicad_uri(project_dir, SYMBOL_DIR / f"{name}.kicad_sym"))
            for name in nicknames
        ]
        footprint_rows = [
            (FOOTPRINT_LIB_NAME, kicad_uri(project_dir, FOOTPRINT_DIR))
        ]
        tables = {
            project_dir / "sym-lib-table": render_lib_table("sym_lib_table", symbol_rows),
            project_dir / "fp-lib-table": render_lib_table("fp_lib_table", footprint_rows),
        }
        for path, contents in tables.items():
            existing = ""
            if path.exists():
                existing = path.read_bytes().decode("utf-8")
            if existing != contents:
                plan.writes.append((path, contents))
                plan.notes.append(f"update {repo_rel(path)}")
            else:
                plan.notes.append(f"current {repo_rel(path)}")


def shared_step_prefix(projects: list[Path]) -> str:
    prefixes: dict[str, list[str]] = {}
    for project_dir in projects:
        try:
            prefix = Path(os.path.relpath(STEP_DIR, project_dir)).as_posix()
        except ValueError as exc:
            raise SystemExit(f"Cannot build a relative path for {repo_rel(project_dir)}: {exc}") from exc
        prefixes.setdefault(prefix, []).append(repo_rel(project_dir))
    if len(prefixes) != 1:
        lines = ["Projects are not at the same depth under the repo, so one shared ${KIPRJMOD} model path will not work:"]
        for prefix, names in sorted(prefixes.items()):
            lines.append(f"  {prefix}")
            lines.extend(f"    {name}" for name in names)
        raise SystemExit("\n".join(lines))
    return next(iter(prefixes))


def require_library_dirs() -> None:
    missing = [path for path in (SYMBOL_DIR, FOOTPRINT_DIR, STEP_DIR) if not path.is_dir()]
    if missing:
        joined = ", ".join(repo_rel(path) for path in missing)
        raise SystemExit(f"Missing library directory: {joined}")


def build_plan() -> tuple[SyncPlan, list[Path]]:
    require_library_dirs()
    projects = find_projects(REPO_ROOT)
    if not projects:
        raise SystemExit(f"No .kicad_pro files under {REPO_ROOT}")
    step_prefix = shared_step_prefix(projects)
    plan = SyncPlan()
    plan.notes.append(
        f"{len(projects)} projects, STEP prefix ${{KIPRJMOD}}/{step_prefix}"
    )
    for project_dir in projects:
        plan.notes.append(f"project {repo_rel(project_dir)}")
    footprint_files = files_by_lower(FOOTPRINT_DIR, ".kicad_mod")
    nicknames = plan_symbols(plan, footprint_files)
    plan_models(plan, step_prefix, discover_step_files())
    plan_tables(plan, projects, nicknames)
    return plan, projects


def apply_writes(plan: SyncPlan) -> None:
    for path, contents in plan.writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents.encode("utf-8"))


def print_plan(plan: SyncPlan, check: bool) -> None:
    print("\n".join(plan.notes))
    file_writes = [path for path, _ in plan.writes]
    if file_writes:
        action = "Would write" if check else "Wrote"
        print(f"{action} {len(file_writes)} files:")
        for path in file_writes:
            print(f"  {repo_rel(path)}")
    else:
        print("Library tables and STEP paths are already current.")
    if plan.warnings:
        print(f"Left unchanged ({len(plan.warnings)}):")
        for warning in plan.warnings:
            print(f"  {warning}")
    else:
        print("No library mismatches.")
    if any(path.suffix == ".kicad_mod" for path, _ in plan.writes) and not check:
        print(
            "Boards keep their own copy of each model path. "
            "In KiCad, use Update Footprints from Library to refresh placed parts."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the writes and mismatches without changing files",
    )
    args = parser.parse_args(argv)
    plan, _projects = build_plan()
    if plan.writes and not args.check:
        apply_writes(plan)
    print_plan(plan, args.check)
    if args.check and plan.writes:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
