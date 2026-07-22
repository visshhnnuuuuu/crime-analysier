"""
Time-Series Trend Forecasting (Phase 9 of the plan)

Aggregates FIR counts by day, runs seasonal decomposition, and flags
anomalies (spikes/drops outside the expected range).
"""

import json
import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose


def load_daily_counts(records_path="records.json"):
    with open(records_path) as f:
        records = json.load(f)

    df = pd.DataFrame(records)
    df["date_filed"] = pd.to_datetime(df["date_filed"])

    daily_counts = df.groupby("date_filed").size()
    full_range = pd.date_range(daily_counts.index.min(), daily_counts.index.max(), freq="D")
    daily_counts = daily_counts.reindex(full_range, fill_value=0)
    daily_counts.index.name = "date"
    return daily_counts


def detect_anomalies(daily_counts, period=30, threshold=2.5):
    decomposition = seasonal_decompose(daily_counts, model="additive", period=period)
    resid = decomposition.resid.dropna()

    std = resid.std()
    mean = resid.mean()

    anomalies = resid[(resid - mean).abs() > threshold * std]

    return decomposition, anomalies


def get_trends(records_path="records.json", period=30, threshold=2.5):
    daily_counts = load_daily_counts(records_path)
    decomposition, anomalies = detect_anomalies(daily_counts, period=period, threshold=threshold)

    trend_line = [
        {"date": str(d.date()), "count": int(c), "trend": float(t) if not np.isnan(t) else None}
        for d, c, t in zip(daily_counts.index, daily_counts.values, decomposition.trend)
    ]

    anomaly_list = [
        {"date": str(d.date()), "actual_count": int(daily_counts.loc[d]), "deviation": float(v)}
        for d, v in anomalies.items()
    ]

    return {
        "trend_line": trend_line,
        "anomalies": anomaly_list,
        "n_anomalies": len(anomaly_list),
    }


if __name__ == "__main__":
    result = get_trends()
    print(f"Found {result['n_anomalies']} anomalies")
    for a in result["anomalies"]:
        print(f"  {a['date']}: {a['actual_count']} cases (deviation: {a['deviation']:.2f})")