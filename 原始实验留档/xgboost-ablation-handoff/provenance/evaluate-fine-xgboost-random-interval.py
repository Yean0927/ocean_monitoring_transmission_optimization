#!/usr/bin/env python3
# Evaluate the second-stage fine-tuned XGBoost parameters on the random-interval
# model-results dataset/split so the numbers are comparable with the previous
# model-training-performance-summary figure.

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_PACKAGES = ROOT / "08_algorithm_docs" / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/ns3-final-submission-matplotlib")

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

BASE_SCRIPT = ROOT / "08_algorithm_docs" / "scripts" / "train-lightweight-protocol-selector.py"
INPUT = ROOT / "05_datasets_and_generators" / "training-data" / "random-interval-anchor-jitter-12000" / "jittered-training-samples-12000.csv"
OUTPUT_DIR = ROOT / "08_algorithm_docs" / "results" / "xgboost-fine-random-interval"


def load_base_module():
    spec = importlib.util.spec_from_file_location("protocol_selector_base", BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base_module()
    df = base.load_dataset(INPUT, max_rows=12000, seed=42)
    train_df, test_df = train_test_split(
        df,
        test_size=0.25,
        random_state=42,
        stratify=df["best_protocol"],
    )
    feature_columns = base.NUMERIC_FEATURES + base.CATEGORICAL_FEATURES
    label_encoder = LabelEncoder()
    label_encoder.fit(base.LABELS)
    y_train = label_encoder.transform(train_df["best_protocol"])
    y_test = test_df["best_protocol"]

    model = Pipeline(
        steps=[
            ("preprocess", base.make_preprocessor()),
            (
                "model",
                XGBClassifier(
                    n_estimators=220,
                    max_depth=11,
                    learning_rate=0.04,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    objective="multi:softprob",
                    eval_metric="mlogloss",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    model.fit(train_df[feature_columns], y_train)
    predictions = label_encoder.inverse_transform(model.predict(test_df[feature_columns]))
    scores = base.scores_from_model(model, test_df[feature_columns], label_encoder)
    metric = base.evaluate_predictions("XGBoost-Fine", y_test, predictions, test_df, scores)
    metric.update(
        {
            "variant": "lr0.04_n220_depth11",
            "params_json": '{"learning_rate": 0.04, "max_depth": 11, "n_estimators": 220}',
            "learning_rate": 0.04,
            "n_estimators": 220,
            "max_depth": 11,
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "input": str(INPUT.relative_to(ROOT)),
        }
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([metric]).to_csv(OUTPUT_DIR / "xgboost-fine-random-interval-metrics.csv", index=False)
    base.write_confusion_matrix(
        OUTPUT_DIR / "confusion-matrix-XGBoost-Fine.csv",
        confusion_matrix(y_test, predictions, labels=base.LABELS),
    )
    (OUTPUT_DIR / "classification-report-XGBoost-Fine.txt").write_text(
        classification_report(y_test, predictions, labels=base.LABELS, zero_division=0)
    )
    print(pd.DataFrame([metric]).to_string(index=False))
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
