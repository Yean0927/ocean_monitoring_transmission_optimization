"""Load the fitted phase-one pipeline and predict from explicit live features.

The caller supplies the current network observation and actual traffic features.
No throughput scaling, nearest-anchor substitution or mean network state is used.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import pandas as pd


class ProtocolSelector:
    def __init__(self, model_dir: Path):
        metadata = json.loads((model_dir / "xgboost-metadata.json").read_text(encoding="utf-8"))
        self.numeric = metadata["numeric_features"]
        self.categorical = metadata["categorical_features"]
        self.labels = metadata["encoded_class_order"]
        self.pipeline = joblib.load(model_dir / "xgboost-protocol-selector.joblib")
        if len(self.labels) != len(self.pipeline.named_steps["model"].classes_):
            raise ValueError("Model classes and label metadata disagree")

    def select(self, features: dict) -> dict:
        columns = self.numeric + self.categorical
        missing = set(columns) - set(features)
        if missing:
            raise ValueError(f"Missing explicit model inputs: {sorted(missing)}")
        row = {name: features[name] for name in columns}
        for name in self.numeric:
            row[name] = float(row[name])
            if not math.isfinite(row[name]):
                raise ValueError(f"Non-finite feature: {name}")
        for name in self.categorical:
            if row[name] is None:
                raise ValueError(f"Missing categorical feature: {name}")
            row[name] = str(row[name])
        probabilities = self.pipeline.predict_proba(pd.DataFrame([row], columns=columns))[0]
        encoded_classes = self.pipeline.named_steps["model"].classes_
        scores = {self.labels[int(label)]: float(probability)
                  for label, probability in zip(encoded_classes, probabilities)}
        return {"protocol": max(scores, key=scores.get), "probabilities": scores,
                "features": row}
