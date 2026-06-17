import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nbformat
from nbconvert import MarkdownExporter, PythonExporter
from config.config import DEFAULT_TARGETS, OUTPUT_MD, OUTPUT_PY, OUTPUT_MD_DIR, OUTPUT_PY_DIR, PROJECT_ROOT


def convert_notebook(notebook_path: Path, md_dir: Path | None = None, py_dir: Path | None = None):
    notebook_path = Path(notebook_path).resolve()
    if not notebook_path.exists():
        print(f"[skip] Not found: {notebook_path}")
        return

    stem = notebook_path.stem

    with open(notebook_path, encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    if OUTPUT_MD:
        out_dir = md_dir if md_dir else notebook_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{stem}.md"
        md_path.write_text(MarkdownExporter().from_notebook_node(nb)[0], encoding="utf-8")
        print(f"[md]  {md_path}")

    if OUTPUT_PY:
        out_dir = py_dir if py_dir else notebook_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        py_path = out_dir / f"{stem}.py"
        py_path.write_text(PythonExporter().from_notebook_node(nb)[0], encoding="utf-8")
        print(f"[py]  {py_path}")


def resolve_targets(targets: list[str]) -> list[Path]:
    paths = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p = p.resolve()
        if p.is_dir():
            paths.extend(sorted(p.glob("*.ipynb")))
        elif p.suffix == ".ipynb":
            paths.append(p)
        else:
            print(f"[warn] Not a notebook or directory: {p}")
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Convert Jupyter notebooks to .md and/or .py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python converter/converter.py\n"
            "  python converter/converter.py converter/raw\n"
            "  python converter/converter.py converter/raw/TCoil_Dataset_Generator_and_Training.ipynb\n"
            "  python converter/converter.py file1.ipynb file2.ipynb some_folder\\"
        ),
    )
    parser.add_argument("targets", nargs="*", help="Notebook files or folders (default: from config)")
    args = parser.parse_args()

    raw_targets = args.targets if args.targets else DEFAULT_TARGETS
    notebooks = resolve_targets(raw_targets)

    if not notebooks:
        print("No notebooks found.")
        return

    md_dir = Path(OUTPUT_MD_DIR).resolve() if OUTPUT_MD_DIR else None
    py_dir = Path(OUTPUT_PY_DIR).resolve() if OUTPUT_PY_DIR else None
    for nb_path in notebooks:
        convert_notebook(nb_path, md_dir, py_dir)


if __name__ == "__main__":
    main()
