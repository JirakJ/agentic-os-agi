import pathlib
import sys

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "scripts"
sys.path.insert(0, str(HOOKS))
