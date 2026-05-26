"""指标层 JSON 持久化存储（可后续替换为 MySQL 元数据库）。"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbi.domain.models import DimensionDefinition, MetricDefinition


class MetricStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {"metrics": [], "dimensions": {}}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)

    def _save_raw(self, data: Dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def seed_if_empty(self, seed_path: Path) -> None:
        if self._path.is_file() and self._metrics_list():
            return
        seed = Path(seed_path)
        if seed.is_file():
            shutil.copy(seed, self._path)

    def _metrics_list(self) -> List[Dict[str, Any]]:
        return self._load_raw().get("metrics") or []

    def list_metrics(self, *, status: Optional[str] = None) -> List[MetricDefinition]:
        out: List[MetricDefinition] = []
        raw = self._load_raw()
        dim_map = raw.get("dimensions") or {}
        for m in self._metrics_list():
            if status and m.get("status") != status:
                continue
            code = m["code"]
            dims = [
                DimensionDefinition(
                    code=d["code"],
                    name=d["name"],
                    column_expr=d["column_expr"],
                )
                for d in dim_map.get(code, [])
            ]
            out.append(
                MetricDefinition(
                    code=code,
                    name=m["name"],
                    dataset_id=m.get("dataset_id", ""),
                    base_table=m["base_table"],
                    expression=m["expression"],
                    format=m.get("format", "number"),
                    description=m.get("description", ""),
                    synonyms=m.get("synonyms") or [],
                    dimensions=[d.code for d in dims],
                    status=m.get("status", "published"),
                )
            )
        return out

    def get_metric(self, code: str) -> Optional[MetricDefinition]:
        for m in self.list_metrics():
            if m.code == code:
                return m
        return None

    def get_dimensions(self, metric_code: str) -> List[DimensionDefinition]:
        raw = self._load_raw()
        dim_map = raw.get("dimensions") or {}
        return [
            DimensionDefinition(
                code=d["code"],
                name=d["name"],
                column_expr=d["column_expr"],
            )
            for d in dim_map.get(metric_code, [])
        ]

    def upsert_metric(self, payload: Dict[str, Any]) -> MetricDefinition:
        data = self._load_raw()
        metrics = data.setdefault("metrics", [])
        code = payload["code"]
        existing_idx = next(
            (i for i, m in enumerate(metrics) if m.get("code") == code), None
        )
        row = {
            "code": code,
            "name": payload["name"],
            "dataset_id": payload.get("dataset_id", ""),
            "base_table": payload["base_table"],
            "expression": payload["expression"],
            "format": payload.get("format", "number"),
            "description": payload.get("description", ""),
            "synonyms": payload.get("synonyms") or [],
            "dimensions": payload.get("dimensions") or [],
            "status": payload.get("status", "published"),
        }
        if existing_idx is not None:
            metrics[existing_idx] = row
        else:
            metrics.append(row)

        if payload.get("dimensions_detail"):
            data.setdefault("dimensions", {})[code] = payload["dimensions_detail"]

        self._save_raw(data)
        m = self.get_metric(code)
        assert m is not None
        return m

    def delete_metric(self, code: str) -> bool:
        data = self._load_raw()
        metrics = data.get("metrics") or []
        new_metrics = [m for m in metrics if m.get("code") != code]
        if len(new_metrics) == len(metrics):
            return False
        data["metrics"] = new_metrics
        dims = data.get("dimensions") or {}
        dims.pop(code, None)
        self._save_raw(data)
        return True
