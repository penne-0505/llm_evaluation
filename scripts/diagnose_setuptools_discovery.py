from pathlib import Path


def _read_pyproject(root: Path) -> str:
    path = root / "pyproject.toml"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _print_top_level_dirs(root: Path) -> None:
    dirs = sorted(
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )
    print("Top-level directories:")
    for name in dirs:
        print(f"- {name}")


def _print_setuptools_discovery(root: Path) -> None:
    try:
        from setuptools.discovery import (  # type: ignore[import-not-found]
            FlatLayoutModuleFinder,
            FlatLayoutPackageFinder,
        )
    except Exception as exc:
        print("Setuptools discovery unavailable:")
        print(f"- {exc.__class__.__name__}: {exc}")
        return

    packages = FlatLayoutPackageFinder.find(str(root))
    modules = FlatLayoutModuleFinder.find(str(root))

    print("Setuptools flat-layout discovery:")
    print(f"- packages: {packages}")
    print(f"- modules: {modules}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(f"Repository root: {root}")

    pyproject_text = _read_pyproject(root)
    print("pyproject.toml sections:")
    print(f"- has [build-system]: {'[build-system]' in pyproject_text}")
    print(f"- has [tool.setuptools]: {'[tool.setuptools]' in pyproject_text}")
    print(
        f"- has [tool.setuptools.packages]: {'[tool.setuptools.packages]' in pyproject_text}"
    )

    _print_top_level_dirs(root)
    _print_setuptools_discovery(root)


if __name__ == "__main__":
    main()
