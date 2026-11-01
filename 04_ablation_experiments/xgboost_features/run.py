"""Load the exported selector or retrain controlled feature ablations."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "jittered-training-samples-12000.csv"
NUMERIC = [
    "rtt_ms", "capacity_mbps", "packet_loss_rate", "phase_progress",
    "loss_trend", "capacity_trend", "rtt_trend", "packet_size_min",
    "packet_size_max", "packet_size_mean", "packet_size_std", "interval_min_ms",
    "interval_max_ms", "interval_mean_ms", "interval_std_ms", "offered_load_mbps",
    "file_size_mb", "effective_file_size_mb", "compression_ratio", "prev_rtt_ms",
    "prev_capacity_mbps", "prev_packet_loss_rate",
]
CATEGORICAL = [
    "source_scenario", "state_name", "interval_mode", "traffic_mode",
    "data_type", "prev_best_protocol",
]
# LabelEncoder in the historical training script uses alphabetical order.
CLASSES = ["QUIC_BBR", "TCP_BBR", "TCP_CUBIC"]
PERFORMANCE = ["quic_bbr_mbps", "tcp_bbr_mbps", "tcp_cubic_mbps"]
PARAMS = dict(
    n_estimators=220, max_depth=11, learning_rate=0.04, subsample=0.85,
    colsample_bytree=0.85, objective="multi:softprob", eval_metric="mlogloss",
    random_state=42, n_jobs=4,
)
PACKET = {c for c in NUMERIC if c.startswith("packet_size_")}
INTERVAL = {c for c in NUMERIC if c.startswith("interval_")}
CONTEXT = {
    "phase_progress", "loss_trend", "capacity_trend", "rtt_trend",
    "prev_rtt_ms", "prev_capacity_mbps", "prev_packet_loss_rate",
    "prev_best_protocol", "source_scenario", "state_name",
}
VARIANTS = {
    "full": set(),
    "no_packet_size": PACKET | {"offered_load_mbps"},
    "no_send_interval": INTERVAL | {"offered_load_mbps", "interval_mode"},
    "no_traffic": PACKET | INTERVAL | {
        "offered_load_mbps", "file_size_mb", "effective_file_size_mb",
        "compression_ratio", "interval_mode", "traffic_mode", "data_type",
    },
    "no_context": CONTEXT,
    "link_only": set(NUMERIC + CATEGORICAL) - {
        "rtt_ms", "capacity_mbps", "packet_loss_rate",
    },
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def normalize(df):
    df = df.copy()
    # Match the historical preprocessing exactly, including absent columns.
    for c in NUMERIC:
        if c not in df:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in CATEGORICAL:
        if c not in df:
            df[c] = "unknown"
        df[c] = df[c].fillna("unknown").astype(str)
    return df


def dataset():
    df = pd.read_csv(DATA)
    df["source_row"] = np.arange(len(df))
    return normalize(df[df.best_protocol.isin(CLASSES)]).reset_index(drop=True)


def split_data(df, mode):
    idx = np.arange(len(df))
    if mode == "legacy-row":
        return train_test_split(idx, test_size=0.25, random_state=42,
                                stratify=df.best_protocol)
    if df.anchor_id.isna().any():
        raise ValueError("Missing anchor_id; grouped split would be invalid")
    return next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
                .split(df, groups=df.anchor_id))


def fit(train, variant):
    removed = VARIANTS[variant]
    nums = [c for c in NUMERIC if c not in removed]
    cats = [c for c in CATEGORICAL if c not in removed]
    transforms = [("num", StandardScaler(), nums)]
    if cats:
        transforms.append(("cat", OneHotEncoder(handle_unknown="ignore"), cats))
    model = Pipeline([
        ("preprocess", ColumnTransformer(transforms)),
        ("model", XGBClassifier(**PARAMS)),
    ])
    labels = train.best_protocol.map({c: i for i, c in enumerate(CLASSES)})
    if set(labels.unique()) != {0, 1, 2}:
        raise ValueError("Training partition must contain all three classes")
    model.fit(train[nums + cats], labels)
    return model, nums + cats


def metrics(test, probabilities):
    predicted = probabilities.argmax(axis=1)
    truth = test.best_protocol.map({c: i for i, c in enumerate(CLASSES)}).to_numpy()
    values = test[PERFORMANCE].to_numpy(dtype=float)
    chosen = values[np.arange(len(test)), predicted].mean()
    oracle = values.max(axis=1).mean()
    return dict(
        accuracy=float(accuracy_score(truth, predicted)),
        macro_f1=float(f1_score(truth, predicted, labels=[0, 1, 2], average="macro")),
        macro_auc=float(roc_auc_score(truth, probabilities, labels=[0, 1, 2],
                                      multi_class="ovr", average="macro")),
        avg_selected_mbps=float(chosen), avg_oracle_mbps=float(oracle),
        oracle_gap_mbps=float(oracle - chosen),
    )


def record_split(df, train_idx, test_idx, out):
    overlap = set(df.iloc[train_idx].anchor_id) & set(df.iloc[test_idx].anchor_id)
    rows = []
    for name, indices in [("train", train_idx), ("test", test_idx)]:
        part = df.iloc[indices][["source_row", "sample_id", "anchor_id"]].copy()
        part["partition"] = name
        part["partition_order"] = np.arange(len(part))
        rows.append(part)
    pd.concat(rows).to_csv(out / "split.csv", index=False)
    return len(overlap)


def export_model(args):
    out = ROOT / "model"
    out.mkdir(exist_ok=True)
    df = dataset()
    train_idx, test_idx = split_data(df, "legacy-row")
    train, test = df.iloc[train_idx], df.iloc[test_idx]
    model, features = fit(train, "full")
    probs = model.predict_proba(test[features])
    result = metrics(test, probs)
    model.named_steps["model"].save_model(out / "xgboost.json")
    joblib.dump(model.named_steps["preprocess"], out / "preprocessor.joblib")
    joblib.dump(model, out / "pipeline.joblib")
    overlap = record_split(df, train_idx, test_idx, out)
    historical = pd.read_csv(ROOT / "provenance" / "historical-metrics.csv").iloc[0]
    delta = {k: result[k] - float(historical[k]) for k in result}
    metadata = dict(
        provenance="Re-trained export; the historical fine-tuning script did not save weights.",
        params=PARAMS, original_n_jobs=-1, export_n_jobs=4,
        class_mapping={str(i): c for i, c in enumerate(CLASSES)},
        numeric_features=NUMERIC, categorical_features=CATEGORICAL,
        transformed_features=model.named_steps["preprocess"].get_feature_names_out().tolist(),
        train_rows=len(train), test_rows=len(test), split="legacy-row",
        overlapping_anchor_count=overlap, metrics=result, historical_metric_delta=delta,
        dataset_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),
        versions=dict(python=platform.python_version(), numpy=np.__version__,
                      pandas=pd.__version__, scikit_learn=sklearn.__version__,
                      xgboost=xgboost.__version__, joblib=joblib.__version__),
    )
    write_json(out / "metadata.json", metadata)
    test[features].head(8).to_csv(ROOT / "example-input.csv", index=False)
    print(json.dumps(metadata, indent=2))


def load_export():
    preprocessor = joblib.load(ROOT / "model" / "preprocessor.joblib")
    model = XGBClassifier()
    model.load_model(ROOT / "model" / "xgboost.json")
    return preprocessor, model


def verify(args):
    meta = json.loads((ROOT / "model" / "metadata.json").read_text())
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == meta["dataset_sha256"]
    df = dataset().set_index("source_row", drop=False)
    split = pd.read_csv(ROOT / "model" / "split.csv")
    ids = split[split.partition == "test"].sort_values("partition_order").source_row
    test = df.loc[ids]
    pre, model = load_export()
    probabilities = model.predict_proba(pre.transform(test[NUMERIC + CATEGORICAL]))
    pipeline = joblib.load(ROOT / "model" / "pipeline.joblib")
    np.testing.assert_allclose(probabilities, pipeline.predict_proba(test[NUMERIC + CATEGORICAL]))
    result = metrics(test, probabilities)
    for k, v in result.items():
        np.testing.assert_allclose(v, meta["metrics"][k], atol=1e-9)
    print("PASS: data hash, JSON model, preprocessing, pipeline, and held-out metrics")
    print(json.dumps(result, indent=2))


def predict(args):
    raw = pd.read_csv(args.input)
    missing = set(NUMERIC + CATEGORICAL) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing input features: {sorted(missing)}")
    pre, model = load_export()
    prob = model.predict_proba(pre.transform(normalize(raw)[NUMERIC + CATEGORICAL]))
    result = pd.DataFrame(prob, columns=[f"prob_{c}" for c in CLASSES])
    result["predicted_protocol"] = np.asarray(CLASSES)[prob.argmax(axis=1)]
    result.to_csv(args.output, index=False)
    print(result.to_string(index=False))


def ablate(args):
    out = ROOT / "results" / args.split
    out.mkdir(parents=True, exist_ok=True)
    df = dataset()
    tr, te = split_data(df, args.split)
    overlap = record_split(df, tr, te, out)
    if args.split == "anchor":
        assert overlap == 0
    results = []
    for variant in args.variants:
        model, features = fit(df.iloc[tr], variant)
        row = dict(variant=variant, feature_count=len(features), split=args.split,
                   train_rows=len(tr), test_rows=len(te), overlapping_anchors=overlap,
                   **metrics(df.iloc[te], model.predict_proba(df.iloc[te][features])))
        results.append(row)
        print(json.dumps(row), flush=True)
        model.named_steps["model"].save_model(out / f"{variant}.json")
        write_json(out / f"{variant}-features.json", features)
        joblib.dump(model, out / f"{variant}-pipeline.joblib")
    pd.DataFrame(results).to_csv(out / "ablation-metrics.csv", index=False)
    write_json(out / "run-config.json", dict(
        params=PARAMS, variants=args.variants, split=args.split,
        dataset_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export").set_defaults(func=export_model)
    sub.add_parser("verify").set_defaults(func=verify)
    p = sub.add_parser("predict")
    p.add_argument("--input", type=Path, default=ROOT / "example-input.csv")
    p.add_argument("--output", type=Path, default=ROOT / "predictions.csv")
    p.set_defaults(func=predict)
    p = sub.add_parser("ablate")
    p.add_argument("--split", choices=["anchor", "legacy-row"], default="anchor")
    p.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS))
    p.set_defaults(func=ablate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
