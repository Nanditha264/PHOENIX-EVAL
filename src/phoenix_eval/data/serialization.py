"""Deterministic data serialization and deserialization utilities."""

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
import pandas as pd
from pydantic import BaseModel

from phoenix_eval.core.exceptions import SerializationError

T = TypeVar("T", bound=BaseModel)


class BenchmarkJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder handling datetimes, Enums, Pydantic models, paths, and NumPy objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (set, frozenset)):
            return sorted(obj)
        return super().default(obj)


def serialize_json(data: Any, indent: int = 2) -> str:
    """Serialize any Python object or Pydantic model to a deterministic JSON string."""
    try:
        if isinstance(data, BaseModel):
            return json.dumps(
                data.model_dump(mode="json"),
                indent=indent,
                sort_keys=True,
                ensure_ascii=False,
                cls=BenchmarkJSONEncoder,
            )
        return json.dumps(
            data,
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            cls=BenchmarkJSONEncoder,
        )
    except Exception as err:
        raise SerializationError(f"Failed to serialize object to JSON: {err}") from err


def deserialize_json(text: str) -> Any:
    """Parse JSON string into a Python object with descriptive error handling."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise SerializationError(f"Malformed JSON text: {err}") from err


def write_json(path: Path, data: Any, indent: int = 2) -> Path:
    """Write data to a JSON file deterministically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = serialize_json(data, indent=indent)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            f.write("\n")
        return path
    except Exception as err:
        raise SerializationError(f"Failed to write JSON file '{path}': {err}") from err


def read_json(path: Path) -> Any:
    """Read and deserialize a JSON file."""
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as err:
        raise SerializationError(f"Invalid JSON in file '{path}': {err}") from err
    except Exception as err:
        raise SerializationError(f"Error reading JSON file '{path}': {err}") from err


def write_jsonl(path: Path, items: list[Any]) -> Path:
    """Write a list of items to a JSON Lines file deterministically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                line_data = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                f.write(
                    json.dumps(
                        line_data, sort_keys=True, ensure_ascii=False, cls=BenchmarkJSONEncoder
                    )
                )
                f.write("\n")
        return path
    except Exception as err:
        raise SerializationError(f"Failed to write JSONL file '{path}': {err}") from err


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSON Lines file into a list of dictionaries."""
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    items: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    items.append(json.loads(clean_line))
                except json.JSONDecodeError as err:
                    raise SerializationError(
                        f"Malformed JSONL on line {line_no} of '{path}': {err}"
                    ) from err
        return items
    except Exception as err:
        if isinstance(err, SerializationError):
            raise
        raise SerializationError(f"Error reading JSONL file '{path}': {err}") from err


def write_csv(path: Path, df: pd.DataFrame) -> Path:
    """Write pandas DataFrame to CSV deterministically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8")
        return path
    except Exception as err:
        raise SerializationError(f"Failed to write CSV file '{path}': {err}") from err


def read_csv(path: Path) -> pd.DataFrame:
    """Read CSV file into pandas DataFrame."""
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    try:
        return pd.read_csv(path, encoding="utf-8")
    except Exception as err:
        raise SerializationError(f"Error reading CSV file '{path}': {err}") from err
