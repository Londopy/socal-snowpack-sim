"""Load the model's named thresholds and rates from params.toml."""
import os
import tomllib
from dataclasses import make_dataclass

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.toml")


def _frozen(name, table):
    cls = make_dataclass(name, [(k, type(v)) for k, v in table.items()], frozen=True)
    return cls(**table)


def load_params(path=None):
    """Read a parameter file (the packaged params.toml by default) into frozen dataclasses."""
    with open(path or DEFAULT, "rb") as f:
        raw = tomllib.load(f)
    sections = {k: _frozen(k.title(), v) for k, v in raw.items()}
    return _frozen("Params", sections)
