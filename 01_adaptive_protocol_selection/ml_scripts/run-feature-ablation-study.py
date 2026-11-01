#!/usr/bin/env python3
"""Run a controlled feature ablation study for protocol selection."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))


import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import label_binarize
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler


LABELS = ["TCP_CUBIC", "TCP_BBR", "QUIC_BBR"]
THROUGHPUT_COLUMNS = {
    "TCP_CUBIC": "tcp_cubic_mbps",
    "TCP_BBR": "tcp_bbr_mbps",
    "QUIC_BBR": "quic_bbr_mbps",
}

NUMERIC_FEATURES = [
    "rtt_ms",
    "capacity_mbps",
    "packet_loss_rate",
    "phase_progress",
    "loss_trend",
    "capacity_trend",
    "rtt_trend",
    "packet_size_min",
    "packet_size_max",
    "packet_size_mean",
    "packet_size_std",
    "interval_min_ms",
    "interval_max_ms",
    "interval_mean_ms",
    "interval_std_ms",
    "offered_load_mbps",
    "file_size_mb",
    "effective_file_size_mb",
    "compression_ratio",
    "prev_rtt_ms",
    "prev_capacity_mbps",
    "prev_packet_loss_rate",
]
CATEGORICAL_FEATURES = [
    "source_scenario",
    "state_name",
    "interval_mode",
    "traffic_mode",
    "data_type",
    "prev_best_protocol",
]

PACKET_FEATURES = {"packet_size_min", "packet_size_max", "packet_size_mean", "packet_size_std"}
INTERVAL_FEATURES = {
    "interval_min_ms",
    "interval_max_ms",
    "interval_mean_ms",
    "interval_std_ms",
    "offered_load_mbps",
}
TRAFFIC_NUMERIC_FEATURES = PACKET_FEATURES | INTERVAL_FEATURES | {
    "file_size_mb",
    "effective_file_size_mb",
    "compression_ratio",
}
HISTORY_NUMERIC_FEATURES = {
    "phase_progress",
    "loss_trend",
    "capacity_trend",
    "rtt_trend",
    "prev_rtt_ms",
    "prev_capacity_mbps",
    "prev_packet_loss_rate",
}
TRAFFIC_CATEGORICAL_FEATURES = {"interval_mode", "traffic_mode", "data_type"}
HISTORY_CATEGORICAL_FEATURES = {"source_scenario", "state_name", "prev_best_protocol"}


ABLATIONS = [
    {
        "name": "full_features",
        "description": "All link, traffic, context, and previous-state features",
        "drop_numeric": set(),
        "drop_categorical": set(),
    },
    {
        "name": "link_only",
        "description": "Only RTT, capacity, and packet-loss rate",
        "keep_numeric": {"rtt_ms", "capacity_mbps", "packet_loss_rate"},
        "keep_categorical": set(),
    },
    {
        "name": "no_packet_size",
        "description": "Remove packet-size range and packet-size statistics",
        "drop_numeric": PACKET_FEATURES,
        "drop_categorical": set(),
    },
    {
        "name": "no_send_interval",
        "description": "Remove send-interval features and derived offered load",
        "drop_numeric": INTERVAL_FEATURES,
        "drop_categorical": {"interval_mode"},
    },
    {
        "name": "no_traffic_features",
        "description": "Remove packet size, send interval, offered load, file size, and data-type fields",
        "drop_numeric": TRAFFIC_NUMERIC_FEATURES,
        "drop_categorical": TRAFFIC_CATEGORICAL_FEATURES,
    },
    {
        "name": "no_history_context",
        "description": "Remove phase/trend/previous-window context fields",
        "drop_numeric": HISTORY_NUMERIC_FEATURES,
        "drop_categorical": HISTORY_CATEGORICAL_FEATURES,
    },
]




def load_dataset(path: Path, max_rows: int, seed: int) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["best_protocol"].isin(LABELS)].copy()
    if max_rows and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=seed).reset_index(drop=True)
    for column in NUMERIC_FEATURES:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    for column in CATEGORICAL_FEATURES:
        if column not in df.columns:
            df[column] = "unknown"
        df[column] = df[column].fillna("unknown").astype(str)
    for column in THROUGHPUT_COLUMNS.values():
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df


def feature_set(spec: dict) -> tuple[list[str], list[str]]:
    if "keep_numeric" in spec:
        numeric = [feature for feature in NUMERIC_FEATURES if feature in spec["keep_numeric"]]
        categorical = [feature for feature in CATEGORICAL_FEATURES if feature in spec["keep_categorical"]]
        return numeric, categorical
    numeric = [feature for feature in NUMERIC_FEATURES if feature not in spec["drop_numeric"]]
    categorical = [feature for feature in CATEGORICAL_FEATURES if feature not in spec["drop_categorical"]]
    return numeric, categorical


def selected_throughput(test_df: pd.DataFrame, predictions: list[str]) -> float:
    values = []
    for index, protocol in enumerate(predictions):
        values.append(float(test_df.iloc[index][THROUGHPUT_COLUMNS[protocol]]))
    return float(np.mean(values))


def oracle_throughput(test_df: pd.DataFrame) -> float:
    values = []
    for _index, row in test_df.iterrows():
        values.append(float(row[THROUGHPUT_COLUMNS[row["best_protocol"]]]))
    return float(np.mean(values))


def auc_metrics(y_true, scores):
    try:
        y_binary = label_binarize(y_true, classes=LABELS)
        return roc_auc_score(y_binary, scores, average="macro")
    except ValueError:
        return float("nan")


def evaluate(name: str, description: str, y_true, predictions, test_df, scores, feature_count: int) -> dict:
    avg_selected = selected_throughput(test_df, list(predictions))
    avg_oracle = oracle_throughput(test_df)
    return {
        "ablation": name,
        "description": description,
        "feature_count": feature_count,
        "accuracy": accuracy_score(y_true, predictions),
        "macro_f1": f1_score(y_true, predictions, labels=LABELS, average="macro", zero_division=0),
        "macro_precision": precision_score(y_true, predictions, labels=LABELS, average="macro", zero_division=0),
        "macro_recall": recall_score(y_true, predictions, labels=LABELS, average="macro", zero_division=0),
        "macro_auc": auc_metrics(y_true, scores),
        "avg_selected_mbps": avg_selected,
        "avg_oracle_mbps": avg_oracle,
        "oracle_gap_mbps": avg_oracle - avg_selected,
    }


def train_ablation(spec: dict, train_df: pd.DataFrame, test_df: pd.DataFrame, seed: int, fast: bool) -> dict:
    numeric, categorical = feature_set(spec)
    features = numeric + categorical
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ],
        remainder="drop",
    )
    estimator = LGBMClassifier(
        n_estimators=80 if fast else 220,
        learning_rate=0.06,
        num_leaves=31,
        objective="multiclass",
        random_state=seed,
        verbosity=-1,
    )
    label_encoder = LabelEncoder()
    label_encoder.fit(LABELS)
    y_train = label_encoder.transform(train_df["best_protocol"])
    y_test = test_df["best_protocol"]
    model = Pipeline([("preprocess", preprocessor), ("model", estimator)])
    model.fit(train_df[features], y_train)
    predictions = label_encoder.inverse_transform(model.predict(test_df[features]))
    raw_scores = model.predict_proba(test_df[features])
    scores = np.zeros((len(test_df), len(LABELS)))
    for label in LABELS:
        encoded_index = int(label_encoder.transform([label])[0])
        scores[:, LABELS.index(label)] = raw_scores[:, encoded_index]
    return evaluate(
        spec["name"],
        spec["description"],
        y_test,
        predictions,
        test_df,
        scores,
        len(features),
    )


def static_baselines(test_df: pd.DataFrame) -> list[dict]:
    rows = []
    y_true = test_df["best_protocol"]
    for protocol in LABELS:
        predictions = [protocol] * len(test_df)
        scores = np.zeros((len(test_df), len(LABELS)))
        scores[:, LABELS.index(protocol)] = 1.0
        rows.append(evaluate(f"static_{protocol.lower()}", f"Always select {protocol}", y_true, predictions, test_df, scores, 0))
    return rows




def write_report(metrics_df: pd.DataFrame, output: Path, train_size: int, test_size: int) -> None:
    learned = metrics_df[~metrics_df["ablation"].str.startswith("static_")].copy()
    full = learned[learned["ablation"] == "full_features"].iloc[0]
    best = learned.sort_values(["avg_selected_mbps", "macro_f1"], ascending=False).iloc[0]
    with output.open("w") as stream:
        stream.write("# Feature Ablation Study\n\n")
        stream.write("This experiment uses the same dataset, train/test split, model family, and metrics for every run. Only the input feature group changes.\n\n")
        stream.write(f"- Model: LightGBM\n")
        stream.write(f"- Training samples: {train_size}\n")
        stream.write(f"- Test samples: {test_size}\n")
        stream.write("- Labels: TCP_CUBIC, TCP_BBR, QUIC_BBR\n\n")
        stream.write("## Results\n\n")
        stream.write("| Setting | Feature count | Macro F1 | Macro AUC | Avg selected Mbit/s | Oracle gap Mbit/s | Meaning |\n")
        stream.write("| --- | ---: | ---: | ---: | ---: | ---: | --- |\n")
        for _idx, row in metrics_df.iterrows():
            stream.write(
                f"| {row['ablation']} | {int(row['feature_count'])} | {row['macro_f1']:.3f} | "
                f"{row['macro_auc']:.3f} | {row['avg_selected_mbps']:.3f} | "
                f"{row['oracle_gap_mbps']:.3f} | {row['description']} |\n"
            )
        stream.write("\n## Conclusion\n\n")
        stream.write(
            f"The full-feature model reaches Macro F1 {full['macro_f1']:.3f}, selected throughput "
            f"{full['avg_selected_mbps']:.3f} Mbit/s, and oracle gap {full['oracle_gap_mbps']:.3f} Mbit/s. "
        )
        stream.write(
            f"The best throughput setting is `{best['ablation']}`, with selected throughput "
            f"{best['avg_selected_mbps']:.3f} Mbit/s and oracle gap {best['oracle_gap_mbps']:.3f} Mbit/s. "
        )
        stream.write(
            "Feature groups whose removal lowers Macro F1 or increases oracle gap are useful for adaptive protocol selection.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="sample_results/training_data/jittered-training-samples-12000.csv",
    )
    parser.add_argument("--output-dir", default="sample_results/ablation_results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-ratio", type=float, default=0.25)
    parser.add_argument("--max-rows", type=int, default=12000)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_dataset(ROOT / args.input, args.max_rows, args.seed)
    train_df, test_df = train_test_split(
        df,
        test_size=args.test_ratio,
        random_state=args.seed,
        stratify=df["best_protocol"],
    )

    rows = []
    for spec in ABLATIONS:
        print(f"Running ablation: {spec['name']}", flush=True)
        rows.append(train_ablation(spec, train_df, test_df, args.seed, args.fast))
    rows.extend(static_baselines(test_df))
    metrics_df = pd.DataFrame(rows)
    metrics_df = metrics_df.sort_values(["macro_f1", "avg_selected_mbps"], ascending=False)
    metrics_df.to_csv(output_dir / "feature-ablation-metrics.csv", index=False)
    write_report(metrics_df, output_dir / "feature-ablation-report.md", len(train_df), len(test_df))
    pass  # Figure output omitted from this code package.
    print(output_dir)


if __name__ == "__main__":
    main()
