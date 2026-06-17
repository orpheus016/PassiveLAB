from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Default targets when no CLI args given — files or folders, relative to PROJECT_ROOT
DEFAULT_TARGETS = [
    "converter/raw",
]

OUTPUT_MD = True
OUTPUT_PY = True

# Output directories — None means same folder as each source notebook
OUTPUT_MD_DIR = "converter/output/markdown"
OUTPUT_PY_DIR = "converter/output/python"
