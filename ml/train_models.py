"""
OrchestrAI — ML Anomaly Detection Training Script
==================================================
Trains IsolationForest + RandomForestClassifier on pipeline run data.

DATA PRIORITY (real data first, synthetic fallback):
  1. Reads from pipeline_runs table in PostgreSQL (real runs seeded by seed_demo.py)
  2. Falls back to 2000 synthetic records if DB is unavailable

This means IsolationForest is trained on actual pipeline behaviour, not noise.
"""
import json
import os
import pickle
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
N_SAMPLES    = 2000
ANOMALY_RATE = 0.15
N_ANOMALY    = int(N_SAMPLES * ANOMALY_RATE)
N_EACH       = N_ANOMALY // 5
N_NORMAL     = N_SAMPLES - N_ANOMALY

ML_DIR = Path(__file__).parent
ML_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "records_loaded",
    "records_failed",
    "duration_seconds",
    "hour_of_day",
    "day_of_week",
    "source_type",
    "success_flag",
]

LABEL_NAMES = [
    "NORMAL",
    "ZERO_LOAD",
    "ROW_COUNT_DROP",
    "NULL_SPIKE",
    "PIPELINE_DELAY",
    "CONSECUTIVE_FAILURES",
]

rng = np.random.default_rng(RANDOM_STATE)


# ── Real data loader ──────────────────────────────────────────────────────────

def _load_real_pipeline_runs() -> pd.DataFrame | None:
    """Try to load pipeline_runs from PostgreSQL. Returns None if unavailable."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "orchestrai"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
            connect_timeout=5,
        )
        df = pd.read_sql_query(
            """
            SELECT
                COALESCE(records_loaded, records_ingested, 0)  AS records_loaded,
                COALESCE(records_failed, 0)                    AS records_failed,
                COALESCE(duration_seconds, 120)                AS duration_seconds,
                EXTRACT(HOUR FROM started_at)::int             AS hour_of_day,
                EXTRACT(DOW  FROM started_at)::int             AS day_of_week,
                CASE status WHEN 'success' THEN 1 ELSE 0 END   AS success_flag,
                CASE
                    WHEN status = 'failed' AND COALESCE(records_loaded, records_ingested, 0) < 10
                        THEN 'ZERO_LOAD'
                    WHEN status = 'failed' AND duration_seconds > 600
                        THEN 'PIPELINE_DELAY'
                    WHEN status = 'failed' AND COALESCE(records_failed, 0) > 10
                        THEN 'NULL_SPIKE'
                    WHEN status = 'failed'
                        THEN 'CONSECUTIVE_FAILURES'
                    ELSE 'NORMAL'
                END AS label
            FROM pipeline_runs
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 500
            """,
            conn,
        )
        conn.close()
        if len(df) >= 20:
            print(f"Loaded {len(df)} real pipeline_runs from PostgreSQL.")
            return df
        print(f"Only {len(df)} rows in pipeline_runs — augmenting with synthetic data.")
        return df if len(df) > 0 else None
    except Exception as e:
        print(f"Could not load real pipeline_runs ({e}) — using synthetic data.")
        return None


# ────────────────────────────────────────────────────────────────────────────
# 1. DATA GENERATION
# ────────────────────────────────────────────────────────────────────────────

def _base_cols(n: int) -> dict:
    return dict(
        records_loaded   = rng.integers(5_000, 50_001, size=n),
        records_failed   = rng.integers(0, 51, size=n),
        duration_seconds = rng.uniform(30, 300, size=n),
        hour_of_day      = np.clip(rng.normal(9, 3, size=n).astype(int), 0, 23),
        day_of_week      = rng.integers(0, 7, size=n),
        source_type      = rng.integers(0, 4, size=n),
        success_flag     = rng.choice([0, 1], size=n, p=[0.05, 0.95]),
    )


def generate_normal(n: int) -> pd.DataFrame:
    d = _base_cols(n); d["label"] = "NORMAL"
    return pd.DataFrame(d)


def generate_zero_load(n: int) -> pd.DataFrame:
    """Completely silent success — records_loaded=0, short duration."""
    d = _base_cols(n)
    d["records_loaded"]   = 0
    d["success_flag"]     = 1
    d["duration_seconds"] = rng.uniform(1, 8, size=n)   # suspiciously fast
    d["label"]            = "ZERO_LOAD"
    return pd.DataFrame(d)


def generate_row_count_drop(n: int) -> pd.DataFrame:
    """records_loaded = 10-25% of normal (extreme drop)."""
    d = _base_cols(n)
    normal_vals = rng.integers(5_000, 50_001, size=n)
    drop_factor = rng.uniform(0.08, 0.22, size=n)      # 78–92% drop
    d["records_loaded"] = (normal_vals * drop_factor).astype(int)
    d["records_failed"] = rng.integers(0, 20, size=n)
    d["label"]          = "ROW_COUNT_DROP"
    return pd.DataFrame(d)


def generate_null_spike(n: int) -> pd.DataFrame:
    """records_failed >> 500, loaded OK."""
    d = _base_cols(n)
    d["records_failed"] = rng.integers(1_000, 10_001, size=n)
    d["label"]          = "NULL_SPIKE"
    return pd.DataFrame(d)


def generate_pipeline_delay(n: int) -> pd.DataFrame:
    """duration_seconds >> 800."""
    d = _base_cols(n)
    d["duration_seconds"] = rng.uniform(900, 3_600, size=n)
    d["label"]             = "PIPELINE_DELAY"
    return pd.DataFrame(d)


def generate_consecutive_failures(n: int) -> pd.DataFrame:
    """success_flag=0, records_loaded=0, short duration."""
    d = _base_cols(n)
    d["success_flag"]     = 0
    d["records_loaded"]   = 0
    d["duration_seconds"] = rng.uniform(1, 15, size=n)
    d["label"]            = "CONSECUTIVE_FAILURES"
    return pd.DataFrame(d)


def build_dataset() -> pd.DataFrame:
    # Try real data first
    real_df = _load_real_pipeline_runs()

    if real_df is not None and len(real_df) >= 50:
        # Augment real data with synthetic to reach N_SAMPLES for stable training
        n_synthetic = max(0, N_SAMPLES - len(real_df))
        if n_synthetic > 0:
            n_anom = int(n_synthetic * ANOMALY_RATE)
            n_each = max(1, n_anom // 5)
            n_norm = n_synthetic - n_anom * 5
            synth_parts = [
                generate_normal(n_norm),
                generate_zero_load(n_each),
                generate_row_count_drop(n_each),
                generate_null_spike(n_each),
                generate_pipeline_delay(n_each),
                generate_consecutive_failures(n_each),
            ]
            synth_df = pd.concat(synth_parts, ignore_index=True)
            # add source_type column to real_df if missing
            if "source_type" not in real_df.columns:
                real_df["source_type"] = 0
            df = pd.concat([real_df, synth_df], ignore_index=True)
        else:
            if "source_type" not in real_df.columns:
                real_df["source_type"] = 0
            df = real_df
        df = df.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
        print(f"Dataset: {len(real_df)} real + {len(df)-len(real_df)} synthetic rows")
    else:
        # Pure synthetic fallback
        print(f"Generating {N_NORMAL} normal + {N_ANOMALY} anomalous synthetic samples…")
        parts = [
            generate_normal(N_NORMAL),
            generate_zero_load(N_EACH),
            generate_row_count_drop(N_EACH),
            generate_null_spike(N_EACH),
            generate_pipeline_delay(N_EACH),
            generate_consecutive_failures(N_EACH),
        ]
        if real_df is not None and len(real_df) > 0:
            parts.append(real_df)
        df = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    print(f"Dataset size: {len(df)} rows | anomaly rate: {(df['label'] != 'NORMAL').mean():.1%}")
    return df


# ────────────────────────────────────────────────────────────────────────────
# 2. ISOLATION FOREST  (binary: normal vs anomaly)
# ────────────────────────────────────────────────────────────────────────────

def train_isolation_forest(df: pd.DataFrame):
    print("\n── IsolationForest ────────────────────────────────────────")
    X        = df[FEATURES].values.astype(float)
    y_binary = (df["label"] != "NORMAL").astype(int)

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        contamination=0.15,
        n_estimators=200,
        max_samples="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # decision_function: >0 = normal, <0 = anomaly (by sklearn contract)
    raw_preds = model.predict(X_scaled)
    y_pred    = (raw_preds == -1).astype(int)
    scores    = -model.decision_function(X_scaled)   # flip for AUC

    precision = precision_score(y_binary, y_pred, zero_division=0)
    recall    = recall_score(y_binary, y_pred, zero_division=0)
    f1        = f1_score(y_binary, y_pred, zero_division=0)
    roc_auc   = roc_auc_score(y_binary, scores)

    print(f"  Precision : {precision:.4f}")
    print(f"  Recall    : {recall:.4f}")
    print(f"  F1        : {f1:.4f}")
    print(f"  ROC-AUC   : {roc_auc:.4f}")

    with open(ML_DIR / "isolation_forest.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(ML_DIR / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    print("  Saved: isolation_forest.pkl, scaler.pkl")

    return {
        "precision":    round(precision, 4),
        "recall":       round(recall, 4),
        "f1":           round(f1, 4),
        "roc_auc":      round(roc_auc, 4),
        "trained_on":   int(len(df)),
        "anomaly_rate": round(float((df["label"] != "NORMAL").mean()), 4),
        "trained_at":   datetime.now(timezone.utc).isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. RANDOM FOREST CLASSIFIER  (multi-class anomaly type)
# ────────────────────────────────────────────────────────────────────────────

def train_anomaly_classifier(df: pd.DataFrame):
    print("\n── RandomForestClassifier (anomaly type) ──────────────────")

    df_anomaly = df[df["label"] != "NORMAL"]
    df_normal  = df[df["label"] == "NORMAL"].sample(n=len(df_anomaly), random_state=RANDOM_STATE)
    df_clf     = pd.concat([df_anomaly, df_normal], ignore_index=True).sample(
        frac=1, random_state=RANDOM_STATE
    ).reset_index(drop=True)

    print(f"  Classifier training set: {len(df_clf)} rows ({len(df_anomaly)} anomalous + {len(df_normal)} normal)")

    le = LabelEncoder()
    le.fit(LABEL_NAMES)
    y  = le.transform(df_clf["label"])
    X  = df_clf[FEATURES].values.astype(float)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=RANDOM_STATE, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=200,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight="balanced",
        min_samples_leaf=2,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    weighted_f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    accuracy    = float((y_pred == y_test).mean())
    cm          = [row.tolist() for row in __import__("sklearn.metrics", fromlist=["confusion_matrix"])
                   .confusion_matrix(y_test, y_pred, labels=le.transform(LABEL_NAMES))]

    per_class_f1_arr = f1_score(y_test, y_pred, average=None, zero_division=0,
                                labels=le.transform(LABEL_NAMES))
    per_class_f1 = {name: round(float(sc), 4) for name, sc in zip(LABEL_NAMES, per_class_f1_arr)}

    print(f"  Weighted F1 : {weighted_f1:.4f}")
    print(f"  Accuracy    : {accuracy:.4f}")
    print("  Per-class F1:")
    for name, sc in per_class_f1.items():
        print(f"    {name:<25} {sc:.4f}")

    with open(ML_DIR / "anomaly_classifier.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(ML_DIR / "label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)
    print("  Saved: anomaly_classifier.pkl, label_encoder.pkl")

    return {
        "weighted_f1":      round(weighted_f1, 4),
        "accuracy":         round(accuracy, 4),
        "per_class_f1":     per_class_f1,
        "confusion_matrix": cm,
        "trained_on":       int(len(df_clf)),
        "trained_at":       datetime.now(timezone.utc).isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  OrchestrAI — ML Anomaly Detection Training")
    print("=" * 60)

    df = build_dataset()

    if_metrics  = train_isolation_forest(df)
    clf_metrics = train_anomaly_classifier(df)

    metrics = {
        "isolation_forest":   if_metrics,
        "anomaly_classifier": clf_metrics,
    }

    metrics_path = ML_DIR / "model_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Saved: model_metrics.json")

    print("\n" + "=" * 60)
    print("  FINAL METRICS SUMMARY")
    print("=" * 60)
    print(f"  IsolationForest   | Precision={if_metrics['precision']:.4f}  Recall={if_metrics['recall']:.4f}  F1={if_metrics['f1']:.4f}  ROC-AUC={if_metrics['roc_auc']:.4f}")
    print(f"  AnomalyClassifier | Weighted-F1={clf_metrics['weighted_f1']:.4f}  Accuracy={clf_metrics['accuracy']:.4f}")
    print("  Per-class F1:")
    for name, sc in clf_metrics["per_class_f1"].items():
        print(f"    {name:<25} {sc:.4f}")
    print("=" * 60)
    print("  All models and metrics saved to:", ML_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
