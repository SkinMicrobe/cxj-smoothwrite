"""Utilities for smoothwrite text, JSON, and model artifacts."""

from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from typing import Any

from pydantic import BaseModel
import yaml

PathInput = str | PathLike[str]
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def _config_path(filename: str) -> Path:
    """Resolve packaged configuration, with a source-tree compatibility fallback."""
    packaged = PACKAGE_ROOT / "resources" / filename
    return packaged if packaged.is_file() else PROJECT_ROOT / "config" / filename


def ensure_dir(path: PathInput) -> Path:
    """Create a directory if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_text(path: PathInput) -> str:
    """Read UTF-8 text from a file."""
    return Path(path).read_text(encoding="utf-8")


def write_text(path: PathInput, text: str) -> None:
    """Write UTF-8 text, creating the parent directory if needed."""
    file_path = Path(path)
    ensure_dir(file_path.parent)
    file_path.write_text(text, encoding="utf-8")


def read_json(path: PathInput) -> Any:
    """Read and decode a UTF-8 JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: PathInput, data: Any) -> None:
    """Write JSON in a stable, human-readable UTF-8 format."""
    file_path = Path(path)
    ensure_dir(file_path.parent)
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def model_to_json_file(model: BaseModel, path: PathInput) -> None:
    """Serialize a Pydantic model to a human-readable JSON file."""
    if hasattr(model, "model_dump"):
        data = model.model_dump(mode="json")
    else:
        data = json.loads(model.json())
    write_json(path, data)


def read_yaml(path: PathInput) -> dict[str, Any]:
    """Read a UTF-8 YAML mapping."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def load_default_config() -> dict[str, Any]:
    """Load the bundled smoothwrite default configuration."""
    return read_yaml(_config_path("default.yaml"))


def load_journal_style() -> dict[str, Any]:
    """Load the bundled journal display-name configuration."""
    return read_yaml(_config_path("journal_style.yaml"))
