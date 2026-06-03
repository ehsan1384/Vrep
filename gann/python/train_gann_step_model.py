#!/usr/bin/env python3
"""Train a small GRU model that selects the ATR multiplier for Gann step.

The exported ONNX model accepts raw feature sequences shaped as:

    [1, sequence_length, 8]

and returns logits/probabilities for the configured candidate multipliers.
The same feature recipe is implemented in the MQL5 Expert Advisor.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


FEATURE_COLUMNS = [
    "close_open_atr",
    "range_atr",
    "return_atr",
    "rsi_scaled",
    "ema_gap_atr",
    "gann_distance_atr",
    "volume_z",
    "atr_pct",
]


@dataclass(frozen=True)
class TrainingConfig:
    sequence_length: int
    atr_period: int
    rsi_period: int
    fast_ema: int
    slow_ema: int
    gann_lookback: int
    volume_lookback: int
    label_horizon: int
    candidates: tuple[float, ...]


class GannStepGRU(nn.Module):
    def __init__(
        self,
        feature_count: int,
        hidden_size: int,
        class_count: int,
        feature_mean: np.ndarray,
        feature_std: np.ndarray,
    ) -> None:
        super().__init__()
        self.register_buffer(
            "feature_mean",
            torch.as_tensor(feature_mean, dtype=torch.float32).view(1, 1, feature_count),
        )
        self.register_buffer(
            "feature_std",
            torch.as_tensor(feature_std, dtype=torch.float32).view(1, 1, feature_count),
        )
        self.gru = nn.GRU(
            input_size=feature_count,
            hidden_size=hidden_size,
            num_layers=1,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, class_count),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = (x - self.feature_mean) / self.feature_std.clamp_min(1e-6)
        _, hidden = self.gru(x)
        logits = self.head(hidden[-1])
        return torch.softmax(logits, dim=-1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="MT5 exported OHLCV CSV file")
    parser.add_argument("--onnx-out", default=Path("models/gann_step_gru.onnx"), type=Path)
    parser.add_argument("--metadata-out", default=Path("models/gann_step_gru.metadata.json"), type=Path)
    parser.add_argument("--sequence-length", default=50, type=int)
    parser.add_argument("--atr-period", default=14, type=int)
    parser.add_argument("--rsi-period", default=14, type=int)
    parser.add_argument("--fast-ema", default=21, type=int)
    parser.add_argument("--slow-ema", default=55, type=int)
    parser.add_argument("--gann-lookback", default=96, type=int)
    parser.add_argument("--volume-lookback", default=50, type=int)
    parser.add_argument("--label-horizon", default=24, type=int)
    parser.add_argument(
        "--candidates",
        default="0.50,0.75,1.00,1.25,1.50,2.00,2.50,3.00",
        help="Comma-separated ATR multipliers. Must match the EA input.",
    )
    parser.add_argument("--hidden-size", default=48, type=int)
    parser.add_argument("--epochs", default=25, type=int)
    parser.add_argument("--batch-size", default=256, type=int)
    parser.add_argument("--learning-rate", default=1e-3, type=float)
    parser.add_argument("--opset", default=14, type=int, help="ONNX opset version for export")
    parser.add_argument("--validation-ratio", default=0.20, type=float)
    parser.add_argument("--seed", default=260603, type=int)
    return parser.parse_args()


def read_mt5_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [normalize_column_name(c) for c in df.columns]

    rename_map = {
        "date": "date",
        "time": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tickvol": "tick_volume",
        "tick_volume": "tick_volume",
        "vol": "volume",
        "volume": "volume",
        "spread": "spread",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})

    required = {"open", "high", "low", "close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    if "tick_volume" not in df.columns:
        if "volume" in df.columns:
            df["tick_volume"] = df["volume"]
        else:
            df["tick_volume"] = 1.0

    for column in ["open", "high", "low", "close", "tick_volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if {"date", "time"}.issubset(df.columns):
        df["timestamp"] = pd.to_datetime(
            df["date"].astype(str) + " " + df["time"].astype(str),
            errors="coerce",
        )
        df = df.sort_values("timestamp")

    df = df.dropna(subset=["open", "high", "low", "close", "tick_volume"])
    df = df.reset_index(drop=True)
    if len(df) < 500:
        raise ValueError("Need at least 500 bars for a minimally useful training run.")

    return df


def normalize_column_name(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace("<", "")
        .replace(">", "")
        .replace(" ", "_")
        .replace("-", "_")
    )


def add_indicators(df: pd.DataFrame, cfg: TrainingConfig) -> pd.DataFrame:
    out = df.copy()

    previous_close = out["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - previous_close).abs(),
            (out["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = true_range.ewm(alpha=1.0 / cfg.atr_period, adjust=False).mean()

    delta = out["close"].diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / cfg.rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / cfg.rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0.0, np.nan)
    out["rsi"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    out["fast_ema"] = out["close"].ewm(span=cfg.fast_ema, adjust=False).mean()
    out["slow_ema"] = out["close"].ewm(span=cfg.slow_ema, adjust=False).mean()
    out["swing_low"] = out["low"].rolling(cfg.gann_lookback, min_periods=cfg.gann_lookback).min()
    out["swing_high"] = out["high"].rolling(cfg.gann_lookback, min_periods=cfg.gann_lookback).max()
    out["volume_mean"] = out["tick_volume"].rolling(cfg.volume_lookback).mean()
    out["volume_std"] = out["tick_volume"].rolling(cfg.volume_lookback).std(ddof=1)

    return out


def build_features(df: pd.DataFrame, cfg: TrainingConfig) -> pd.DataFrame:
    out = df.copy()
    atr = out["atr"].replace(0.0, np.nan)
    trend_up = out["fast_ema"] >= out["slow_ema"]
    base = np.where(trend_up, out["swing_low"], out["swing_high"])
    rough_step = atr * 1.25
    nearest = base + np.round((out["close"] - base) / rough_step) * rough_step

    out["close_open_atr"] = (out["close"] - out["open"]) / atr
    out["range_atr"] = (out["high"] - out["low"]) / atr
    out["return_atr"] = (out["close"] - out["close"].shift(1)) / atr
    out["rsi_scaled"] = (out["rsi"] - 50.0) / 50.0
    out["ema_gap_atr"] = (out["fast_ema"] - out["slow_ema"]) / atr
    out["gann_distance_atr"] = (out["close"] - nearest) / atr
    out["volume_z"] = (out["tick_volume"] - out["volume_mean"]) / out["volume_std"].replace(0.0, np.nan)
    out["atr_pct"] = out["atr"] / out["close"].replace(0.0, np.nan)

    return out


def build_labels(df: pd.DataFrame, cfg: TrainingConfig) -> pd.Series:
    labels = []
    candidates = np.asarray(cfg.candidates, dtype=np.float64)

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    fast = df["fast_ema"].to_numpy()
    slow = df["slow_ema"].to_numpy()
    swing_low = df["swing_low"].to_numpy()
    swing_high = df["swing_high"].to_numpy()

    for i in range(len(df)):
        if i + cfg.label_horizon >= len(df) or not np.isfinite(atr[i]) or atr[i] <= 0:
            labels.append(np.nan)
            continue

        trend_up = fast[i] >= slow[i]
        future_slice = slice(i + 1, i + cfg.label_horizon + 1)
        future_extreme = np.nanmax(highs[future_slice]) if trend_up else np.nanmin(lows[future_slice])
        base = swing_low[i] if trend_up else swing_high[i]

        if not np.isfinite(base) or not np.isfinite(future_extreme):
            labels.append(np.nan)
            continue

        scores = []
        for multiplier in candidates:
            step = max(atr[i] * multiplier, 1e-8)
            level_index = math.floor((closes[i] - base) / step)
            next_level = base + (level_index + (1 if trend_up else -1)) * step
            alignment_error = abs(future_extreme - next_level) / atr[i]
            overfit_penalty = 0.03 / multiplier
            scores.append(-(alignment_error + overfit_penalty))

        labels.append(int(np.argmax(scores)))

    return pd.Series(labels, index=df.index, dtype="float64")


def make_windows(df: pd.DataFrame, labels: pd.Series, cfg: TrainingConfig) -> tuple[np.ndarray, np.ndarray]:
    feature_frame = df[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    valid_rows = feature_frame.notna().all(axis=1) & labels.notna()

    x_values = feature_frame.to_numpy(dtype=np.float32)
    y_values = labels.to_numpy()

    windows: list[np.ndarray] = []
    targets: list[int] = []

    for end in range(cfg.sequence_length - 1, len(df)):
        start = end - cfg.sequence_length + 1
        if not valid_rows.iloc[start : end + 1].all():
            continue
        windows.append(x_values[start : end + 1])
        targets.append(int(y_values[end]))

    if not windows:
        raise ValueError("No valid training windows were produced. Check CSV quality and parameters.")

    return np.stack(windows), np.asarray(targets, dtype=np.int64)


def split_chronologically(
    x: np.ndarray,
    y: np.ndarray,
    validation_ratio: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not 0.05 <= validation_ratio <= 0.50:
        raise ValueError("--validation-ratio must be between 0.05 and 0.50")

    split_index = int(len(x) * (1.0 - validation_ratio))
    split_index = min(max(split_index, 1), len(x) - 1)
    return x[:split_index], y[:split_index], x[split_index:], y[split_index:]


def train_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    y_valid: np.ndarray,
    args: argparse.Namespace,
) -> tuple[GannStepGRU, dict[str, float]]:
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    mean = x_train.reshape(-1, x_train.shape[-1]).mean(axis=0)
    std = x_train.reshape(-1, x_train.shape[-1]).std(axis=0)
    std = np.where(std < 1e-6, 1.0, std)

    model = GannStepGRU(
        feature_count=x_train.shape[-1],
        hidden_size=args.hidden_size,
        class_count=len(parse_candidates(args.candidates)),
        feature_mean=mean,
        feature_std=std,
    )

    train_ds = TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train))
    valid_x = torch.from_numpy(x_valid)
    valid_y = torch.from_numpy(y_valid)
    loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()

    best_state = None
    best_valid_loss = float("inf")
    best_valid_accuracy = 0.0

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for batch_x, batch_y in loader:
            optimizer.zero_grad(set_to_none=True)
            probabilities = model(batch_x)
            loss = loss_fn(torch.log(probabilities.clamp_min(1e-8)), batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch_x)

        train_loss /= len(train_ds)
        model.eval()
        with torch.no_grad():
            valid_probabilities = model(valid_x)
            valid_loss = loss_fn(torch.log(valid_probabilities.clamp_min(1e-8)), valid_y).item()
            valid_accuracy = (
                valid_probabilities.argmax(dim=1).eq(valid_y).float().mean().item()
            )

        print(
            f"epoch={epoch:03d} train_loss={train_loss:.5f} "
            f"valid_loss={valid_loss:.5f} valid_acc={valid_accuracy:.4f}"
        )

        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            best_valid_accuracy = valid_accuracy
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    metrics = {
        "best_valid_loss": float(best_valid_loss),
        "best_valid_accuracy": float(best_valid_accuracy),
    }
    return model, metrics


def export_onnx(model: GannStepGRU, args: argparse.Namespace) -> None:
    args.onnx_out.parent.mkdir(parents=True, exist_ok=True)
    model.eval()

    dummy = torch.zeros(1, args.sequence_length, len(FEATURE_COLUMNS), dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        args.onnx_out,
        input_names=["features"],
        output_names=["multiplier_probabilities"],
        opset_version=args.opset,
        do_constant_folding=True,
    )
    print(f"wrote {args.onnx_out}")


def write_metadata(
    model: GannStepGRU,
    cfg: TrainingConfig,
    metrics: dict[str, float],
    args: argparse.Namespace,
    sample_count: int,
) -> None:
    args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model": "GRU classifier",
        "sequence_length": cfg.sequence_length,
        "feature_columns": FEATURE_COLUMNS,
        "candidates": list(cfg.candidates),
        "sample_count": sample_count,
        "metrics": metrics,
        "parameters": {
            "atr_period": cfg.atr_period,
            "rsi_period": cfg.rsi_period,
            "fast_ema": cfg.fast_ema,
            "slow_ema": cfg.slow_ema,
            "gann_lookback": cfg.gann_lookback,
            "volume_lookback": cfg.volume_lookback,
            "label_horizon": cfg.label_horizon,
            "hidden_size": args.hidden_size,
        },
        "normalizer": {
            "mean": model.feature_mean.detach().cpu().numpy().reshape(-1).tolist(),
            "std": model.feature_std.detach().cpu().numpy().reshape(-1).tolist(),
        },
    }
    args.metadata_out.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"wrote {args.metadata_out}")


def parse_candidates(raw: str) -> tuple[float, ...]:
    candidates = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if not candidates or any(value <= 0.0 for value in candidates):
        raise ValueError("--candidates must contain positive numbers")
    return candidates


def print_class_distribution(y: Iterable[int], candidates: tuple[float, ...]) -> None:
    counts = np.bincount(np.asarray(list(y), dtype=np.int64), minlength=len(candidates))
    total = counts.sum()
    print("label distribution:")
    for index, count in enumerate(counts):
        pct = 100.0 * count / max(total, 1)
        print(f"  multiplier={candidates[index]:.2f} count={count} pct={pct:.2f}")


def main() -> None:
    args = parse_args()
    candidates = parse_candidates(args.candidates)
    cfg = TrainingConfig(
        sequence_length=args.sequence_length,
        atr_period=args.atr_period,
        rsi_period=args.rsi_period,
        fast_ema=args.fast_ema,
        slow_ema=args.slow_ema,
        gann_lookback=args.gann_lookback,
        volume_lookback=args.volume_lookback,
        label_horizon=args.label_horizon,
        candidates=candidates,
    )

    df = read_mt5_csv(args.csv)
    df = add_indicators(df, cfg)
    df = build_features(df, cfg)
    labels = build_labels(df, cfg)
    x, y = make_windows(df, labels, cfg)
    print(f"windows={len(x)} features={x.shape[-1]} sequence_length={x.shape[1]}")
    print_class_distribution(y, candidates)

    x_train, y_train, x_valid, y_valid = split_chronologically(x, y, args.validation_ratio)
    model, metrics = train_model(x_train, y_train, x_valid, y_valid, args)
    export_onnx(model, args)
    write_metadata(model, cfg, metrics, args, sample_count=len(x))


if __name__ == "__main__":
    main()
