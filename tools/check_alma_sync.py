"""
Check that the five Alma SRU clients share identical core code.

alma-sru-catalogs/scripts/alma_sru.py is the reference. The single-library
skills (umich, princeton, yale, pitt) keep their own copies so each skill can
be installed alone; this script fails if a shared function has drifted.

Run from the repository root:
    python tools/check_alma_sync.py
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "alma-sru-catalogs/scripts/alma_sru.py"
COPIES = [
    ROOT / "umich-library-catalog/scripts/umich_api.py",
    ROOT / "princeton-library-catalog/scripts/princeton_api.py",
    ROOT / "yale-library-catalog/scripts/yale_api.py",
    ROOT / "pitt-library-catalog/scripts/pitt_api.py",
]

# Module-level functions and class methods that must match exactly.
FUNCTIONS = [
    "parse_marc", "_fields", "_sub", "_text", "_vernacular", "_paired", "_display",
    "holdings", "_normalize", "title_matches",
]
METHODS = ["_retry_after_seconds", "_raise_diagnostics", "quote_term", "build_cql", "search_all", "get_record"]
CONSTANTS = ["FIELD_INDEXES", "SORT_KEYS", "MAX_PAGE_SIZE", "NS", "_CJK"]


def definitions(path: Path) -> dict:
    tree = ast.parse(path.read_text())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            found[node.name] = ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    found[f"method:{item.name}"] = ast.dump(item)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            found[f"const:{node.targets[0].id}"] = ast.dump(node.value)
    return found


def main() -> int:
    ref = definitions(REFERENCE)
    names = FUNCTIONS + [f"method:{m}" for m in METHODS] + [f"const:{c}" for c in CONSTANTS]
    problems = []
    for copy in COPIES:
        defs = definitions(copy)
        for name in names:
            if name not in ref:
                problems.append(f"reference is missing {name}")
            elif defs.get(name) != ref[name]:
                problems.append(f"{copy.relative_to(ROOT)}: {name} differs from alma_sru.py")
    for line in dict.fromkeys(problems):
        print(line)
    if problems:
        return 1
    print(f"OK: {len(names)} shared definitions match in {len(COPIES)} copies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
