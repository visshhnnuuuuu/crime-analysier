# 🤖 packages/ml-models — Machine Learning Pipeline

This module houses training, evaluation, and inference code for the analytics engine of the **Criminal Agent Platform**.

---

## 📈 ML Module Breakdown

### 1. Geospatial Hotspots (`packages/ml-models/hotspot/`)
* **Objective**: Identify crime density hotspots based on geographical latitude and longitude coordinates.
* **Technique**: Kernel Density Estimation (KDE) and DBSCAN (Density-Based Spatial Clustering of Applications with Noise) over historical FIR coordinate datasets.

### 2. Crime Trend Forecasting (`packages/ml-models/forecasting/`)
* **Objective**: Forecast crime trends in specific regions/wards for proactive patrol routing.
* **Technique**: Prophet and ARIMA models trained on seasonal crime occurrence historical indexes.

### 3. Risk Flagging (`packages/ml-models/risk_flagging/`)
* **Objective**: Evaluate risk levels and recidivism flags for suspects under human-in-the-loop review.
* **Technique**: Gradient-boosted decision trees (XGBoost) combined with SHAP (SHapley Additive exPlanations) values to provide fully transparent and explainable risk factors, rather than a black-box percentage score.
