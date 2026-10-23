"""Train an AI4I machine-failure classifier (not time-to-failure forecasting)."""
import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, average_precision_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

FEATURES = [
    "Type", "Air temperature [K]", "Process temperature [K]",
    "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]",
]
TARGET = "Machine failure"
# Deliberately exclude UDI, Product ID, and TWF/HDF/PWF/OSF/RNF: these
# identify records or reveal failure outcomes and would bias evaluation.

def prepare_features(df: pd.DataFrame, expected_columns=None) -> pd.DataFrame:
    missing = sorted(set(FEATURES) - set(df.columns))
    if missing:
        raise ValueError(f"Missing input columns: {missing}")
    X = pd.get_dummies(df[FEATURES].copy(), columns=["Type"], dtype=int)
    X.columns = [c.replace("[", "_").replace("]", "") for c in X.columns]
    if expected_columns is not None:
        X = X.reindex(columns=expected_columns, fill_value=0)
    return X

def train(csv_path: str, model_path: str):
    df = pd.read_csv(csv_path)
    if TARGET not in df.columns:
        raise ValueError(f"CSV must contain '{TARGET}'")
    X = prepare_features(df)
    y = df[TARGET].astype(int)
    if y.isna().any() or not set(y.unique()).issubset({0, 1}):
        raise ValueError("Target must contain only 0 and 1")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    model = XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9,
        eval_metric="logloss", random_state=42, n_jobs=2,
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(confusion_matrix(y_test, preds))
    print(classification_report(y_test, preds, digits=3, zero_division=0))
    print(f"PR-AUC (average precision): {average_precision_score(y_test, probs):.3f}")
    out = Path(model_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "columns": list(X.columns), "features": FEATURES}, out)
    print(f"Saved model to {out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/ai4i2020.csv")
    parser.add_argument("--out", default="models/failure_model.joblib")
    args = parser.parse_args()
    train(args.csv, args.out)
