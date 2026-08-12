"""In-package defaults consumed by product code (`cli.py`'s subcommands). Not to be confused
with the repo-root `config/` (dev-tooling data, e.g. benchmark cases -- not installed with the
package). The split mirrors `scripts/`'s own installed-vs-not split: this package ships in the
wheel, the repo-root folder never does (`pyproject.toml`'s `where = ["src"]`).
"""
