import json
from decimal import Decimal

import pandas as pd

from chatbi.core.json_util import dataframe_to_records, json_safe_value


def test_decimal_serializable():
    assert json_safe_value(Decimal("153.5")) == 153.5
    payload = {"data": [{"avg": json_safe_value(Decimal("88.25"))}]}
    json.dumps(payload)


def test_dataframe_with_decimal_column():
    df = pd.DataFrame([{"avg_total_score": Decimal("612.345")}])
    records = dataframe_to_records(df)
    json.dumps({"data": records})
