"""Design principles the code keeps: domain imports stdlib only; render never imports sources."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "inkmap"
THIRD_PARTY = {"numpy", "PIL", "httpx"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0] if not node.module.startswith("inkmap")
                      else node.module)
    return names


def test_domain_depends_on_nothing():
    for path in (PACKAGE / "domain").glob("*.py"):
        for name in imports(path):
            assert name not in THIRD_PARTY, f"{path.name} imports {name}"
            assert not name.startswith("inkmap.") or name.startswith("inkmap.domain"), (
                f"{path.name} imports {name}")


def test_render_never_imports_sources():
    for path in (PACKAGE / "render").glob("*.py"):
        assert not any(n.startswith("inkmap.sources") for n in imports(path)), path.name
