"""将查询结果等数据转为 JSON 可序列化的 Python 类型。"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


def json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if pd.isna(value):
        return None
    return str(value)


def dataframe_to_records(df: pd.DataFrame, *, limit: int = 500) -> list[dict[str, Any]]:
    records = df.head(limit).to_dict(orient="records")
    return [
        {key: json_safe_value(val) for key, val in row.items()}
        for row in records
    ]
