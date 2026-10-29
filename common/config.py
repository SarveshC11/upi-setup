"""Config loader (owner: Person 4, starter version by Person 3 so the pipeline runs).

`load_config(path=None, overrides=None)` merges a YAML file onto configs/default.yaml.
Unknown keys and wrong value types raise ConfigError with the full key path.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


class ConfigError(ValueError):
    pass


class Config(dict):
    """A dict with attribute access: cfg.policy.weights['new_device']."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def to_dict(self) -> dict:
        return _plain(self)


def _plain(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_plain(v) for v in x]
    return x


def _wrap(x: Any) -> Any:
    if isinstance(x, dict):
        return Config({k: _wrap(v) for k, v in x.items()})
    if isinstance(x, list):
        return [_wrap(v) for v in x]
    return x


def _kind(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def _merge(base: dict, over: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        where = f"{path}.{k}" if path else str(k)
        if k not in base:
            raise ConfigError(f"unknown config key: {where}")
        b = base[k]
        if _kind(b) != _kind(v):
            raise ConfigError(f"wrong type for {where}: expected {_kind(b)}, got {_kind(v)}")
        if isinstance(b, dict):
            out[k] = _merge(b, v, where)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> Config:
    with open(DEFAULT_PATH) as f:
        cfg = yaml.safe_load(f)
    if path is not None and Path(path).resolve() != DEFAULT_PATH:
        with open(path) as f:
            cfg = _merge(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = _merge(cfg, overrides)
    return _wrap(cfg)


def with_overrides(cfg: Config, overrides: dict) -> Config:
    return _wrap(_merge(cfg.to_dict(), overrides))
