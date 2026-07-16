"""Locate project data files by name, wherever they live in the repo.

The .csv/.json data files are gitignored and get reorganized into subfolders
(Key Figures/, tested/, nba_api/, ...). Instead of hardcoding a folder, scripts
call find_data("some_file.csv") and it is found anywhere under the repo root.

    from datapaths import find_data
    df = pd.read_csv(find_data("test_dataset_jan_mar.csv"))
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # repo root (this file lives here)
_SKIP = ("__pycache__", "_cache", "/.git/", "/.claude/")


def find_data(name, must=True):
    """First matching file named `name` under the repo root (skips caches/.git).

    Raises FileNotFoundError if missing and must=True, else returns None.
    """
    for hit in sorted(ROOT.rglob(name)):
        if not any(s in str(hit) for s in _SKIP):
            return hit
    if must:
        raise FileNotFoundError(f"{name!r} not found anywhere under {ROOT}")
    return None
