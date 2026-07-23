"""
Repeat-Offender Risk Flagging (Phase 10 of the plan)

Feature-engineers per-accused stats, trains an XGBoost classifier,
and explains every prediction with SHAP — outputs a FLAG with reasons,
never a raw score. Nothing here auto-actions anything; it just flags
for human review.
"""

import json
import pandas as pd
import numpy as np
import xgboost as xgb
import shap


def load_records(records_path="records.json"):
    with open(records_path) as f:
        return json.load(f)


def build_features(records):
    """One row per accused person, aggregating their case history."""
    df = pd.DataFrame(records)
    df["date_filed"] = pd.to_datetime(df["date_filed"])

    features = []
    for name, group in df.groupby("accused_name"):
        group = group.sort_values("date_filed")
        prior_case_count = len(group)
        n_distinct_crime_types = group["crime_type"].nunique()

        if len(group) > 1:
            gaps = group["date_filed"].diff().dt.days.dropna()
            avg_days_between = float(gaps.mean())
        else:
            avg_days_between = 999.0  # only one case on record -> treat as "long gap"

        features.append({
            "accused_name": name,
            "prior_case_count": prior_case_count,
            "n_distinct_crime_types": n_distinct_crime_types,
            "avg_days_between_offenses": avg_days_between,
        })

    return pd.DataFrame(features)


def label_risk(feature_df):
    """
    Ground-truth label for TRAINING ONLY: a composite risk proxy
    combining case volume, crime-type diversity, and offense frequency
    -- not just raw case count -- so the model has multiple genuine
    signals to learn from and SHAP reflects real per-person variation.
    In a real system this would come from actual outcome data, not a
    proxy rule.
    """
    volume_score = (feature_df["prior_case_count"] >= 4).astype(int)
    diversity_score = (feature_df["n_distinct_crime_types"] >= 3).astype(int)
    frequency_score = (feature_df["avg_days_between_offenses"] <= 45).astype(int)

    composite = volume_score + diversity_score + frequency_score
    feature_df["is_risk"] = (composite >= 2).astype(int)
    return feature_df


def train_model(feature_df):
    X = feature_df[["prior_case_count", "n_distinct_crime_types", "avg_days_between_offenses"]]
    y = feature_df["is_risk"]

    n_pos = y.sum()
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.3,
        min_child_weight=1,
        gamma=0,
        reg_lambda=1,
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        eval_metric="logloss",
    )
    model.fit(X, y)
    return model, X

def get_risk_flags(records_path="records.json"):
    """This is what /analytics/risk-flags would call."""
    records = load_records(records_path)
    feature_df = build_features(records)
    feature_df = label_risk(feature_df)

    model, X = train_model(feature_df)
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    flags = []
    for i, row in feature_df.iterrows():
        if predictions[i] != 1:
            continue  # only surface actual flags, not every person

        # Rank features by absolute SHAP contribution for this prediction
        contributions = list(zip(X.columns, shap_values[i]))
        contributions.sort(key=lambda x: -abs(x[1]))

        top_factors = [
            {"factor": humanize_factor(name, row[name]), "impact": float(val)}
            for name, val in contributions[:3]
        ]

        flags.append({
            "accused_name": row["accused_name"],
            "flag": True,               # a flag, not a numeric score
            "top_factors": top_factors,
            "reviewed": False,          # human-review gate — never auto-actioned
        })

    return {"n_flags": len(flags), "flags": flags}


def humanize_factor(name, value):
    labels = {
        "prior_case_count": f"{int(value)} prior case(s) on record",
        "n_distinct_crime_types": f"involved in {int(value)} distinct crime type(s)",
        "avg_days_between_offenses": f"avg. {value:.0f} days between offenses",
    }
    return labels.get(name, f"{name}={value}")

def debug_check(records_path="records.json"):
    records = load_records(records_path)
    feature_df = build_features(records)
    feature_df = label_risk(feature_df)

    model, X = train_model(feature_df)

    print("Feature importances:", model.feature_importances_)
    print("Number of boosted rounds:", model.get_booster().num_boosted_rounds())
    print("\nFirst tree dump:")
    print(model.get_booster().get_dump()[0])


if __name__ == "__main__":
    result = get_risk_flags()
    print(f"Found {result['n_flags']} risk-flagged individuals (pending human review)")
    for f in result["flags"]:
        print(f"\n{f['accused_name']} — FLAGGED (reviewed: {f['reviewed']})")
        for factor in f["top_factors"]:
            print(f"   - {factor['factor']} (impact: {factor['impact']:+.3f})")
