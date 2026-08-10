from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


TCN_SEQUENCE_CHANNELS = (
    "return_atr",
    "body_atr",
    "range_atr",
    "close_location_centered",
    "wick_balance_atr",
)


class _CausalTCN(nn.Module):
    def __init__(self, input_channels: int, hidden_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(
            input_channels, hidden_channels, kernel_size=3, padding=2
        )
        self.conv2 = nn.Conv1d(
            hidden_channels,
            hidden_channels,
            kernel_size=3,
            dilation=2,
            padding=4,
        )
        self.activation = nn.ReLU()
        self.output = nn.Linear(hidden_channels * 2, 1)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        length = values.shape[-1]
        hidden = self.activation(self.conv1(values)[..., :length])
        hidden = self.activation(self.conv2(hidden)[..., :length])
        pooled = torch.cat((hidden[..., -1], hidden.mean(dim=-1)), dim=1)
        return self.output(pooled).squeeze(1)


class _CausalTransformer(nn.Module):
    def __init__(
        self,
        input_channels: int,
        sequence_length: int,
        model_dimension: int,
        attention_heads: int,
        encoder_layers: int,
        feedforward_dimension: int,
    ) -> None:
        super().__init__()
        self.input_projection = nn.Linear(input_channels, model_dimension)
        self.position_embedding = nn.Parameter(
            torch.empty(1, sequence_length, model_dimension)
        )
        nn.init.normal_(self.position_embedding, mean=0.0, std=0.02)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=model_dimension,
            nhead=attention_heads,
            dim_feedforward=feedforward_dimension,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=encoder_layers,
            enable_nested_tensor=False,
        )
        self.output_normalization = nn.LayerNorm(model_dimension)
        self.output = nn.Linear(model_dimension, 1)
        causal_mask = torch.triu(
            torch.ones(sequence_length, sequence_length, dtype=torch.bool),
            diagonal=1,
        )
        self.register_buffer("causal_mask", causal_mask)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        hidden = self.input_projection(values) + self.position_embedding
        encoded = self.encoder(hidden, mask=self.causal_mask)
        return self.output(self.output_normalization(encoded[:, -1])).squeeze(1)


class _CausalGRU(nn.Module):
    def __init__(self, input_channels: int, hidden_channels: int) -> None:
        super().__init__()
        self.recurrent = nn.GRU(
            input_size=input_channels,
            hidden_size=hidden_channels,
            num_layers=1,
            batch_first=True,
        )
        self.output = nn.Linear(hidden_channels, 1)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        _, final_hidden = self.recurrent(values)
        return self.output(final_hidden[-1]).squeeze(1)


@dataclass
class CausalTCNClassifier:
    sequence_length: int
    hidden_channels: int
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    random_state: int
    channel_names: tuple[str, ...] = TCN_SEQUENCE_CHANNELS
    model_: _CausalTCN | None = field(default=None, init=False)
    channel_mean_: np.ndarray | None = field(default=None, init=False)
    channel_std_: np.ndarray | None = field(default=None, init=False)
    training_loss_: list[float] = field(default_factory=list, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"), init=False
    )

    def _ordered_columns(self) -> list[str]:
        return [
            f"tcn_{channel}_lag_{lag}"
            for lag in reversed(range(self.sequence_length))
            for channel in self.channel_names
        ]

    def _sequence_array(self, values: pd.DataFrame) -> np.ndarray:
        columns = self._ordered_columns()
        missing = sorted(set(columns) - set(values.columns))
        if missing:
            raise ValueError("TCN input is missing sequence columns: " + ", ".join(missing))
        array = values[columns].to_numpy(dtype="float32", copy=True)
        if not np.isfinite(array).all():
            raise ValueError("TCN sequence values must be finite")
        return array.reshape(len(values), self.sequence_length, len(self.channel_names))

    def _standardize(self, sequence: np.ndarray) -> np.ndarray:
        if self.channel_mean_ is None or self.channel_std_ is None:
            raise ValueError("TCN standardization has not been fitted")
        standardized = (sequence - self.channel_mean_) / self.channel_std_
        return np.ascontiguousarray(standardized.transpose(0, 2, 1), dtype="float32")

    def fit(
        self,
        values: pd.DataFrame,
        labels: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> CausalTCNClassifier:
        if self.sequence_length <= 0 or self.hidden_channels <= 0:
            raise ValueError("TCN sequence_length and hidden_channels must be positive")
        if self.epochs <= 0 or self.batch_size <= 0:
            raise ValueError("TCN epochs and batch_size must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError("TCN learning_rate must be positive and weight_decay non-negative")
        target = np.asarray(labels, dtype="float32")
        if len(target) != len(values) or np.unique(target).size != 2:
            raise ValueError("TCN training target must align and contain both classes")
        sequence = self._sequence_array(values)
        self.channel_mean_ = sequence.mean(axis=(0, 1), keepdims=True)
        channel_std = sequence.std(axis=(0, 1), keepdims=True)
        self.channel_std_ = np.maximum(channel_std, 1e-6)
        inputs = torch.from_numpy(self._standardize(sequence))
        targets = torch.from_numpy(target)
        if sample_weight is None:
            weights = torch.ones_like(targets)
        else:
            raw_weights = np.asarray(sample_weight, dtype="float32")
            if (
                raw_weights.shape != target.shape
                or not np.isfinite(raw_weights).all()
            ):
                raise ValueError("TCN sample weights must be finite and align with labels")
            weights = torch.from_numpy(raw_weights)

        torch.manual_seed(self.random_state)
        generator = torch.Generator().manual_seed(self.random_state)
        self.model_ = _CausalTCN(len(self.channel_names), self.hidden_channels)
        optimizer = torch.optim.AdamW(
            self.model_.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        loss_function = nn.BCEWithLogitsLoss(reduction="none")
        loader = DataLoader(
            TensorDataset(inputs, targets, weights),
            batch_size=self.batch_size,
            shuffle=True,
            generator=generator,
            num_workers=0,
        )
        self.training_loss_.clear()
        self.model_.train()
        for _ in range(self.epochs):
            total_loss = 0.0
            total_weight = 0.0
            for batch_inputs, batch_targets, batch_weights in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model_(batch_inputs)
                individual_loss = loss_function(logits, batch_targets)
                loss = (individual_loss * batch_weights).sum() / batch_weights.sum()
                loss.backward()
                optimizer.step()
                total_loss += float((individual_loss.detach() * batch_weights).sum())
                total_weight += float(batch_weights.sum())
            self.training_loss_.append(total_loss / total_weight)
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("TCN model has not been fitted")
        sequence = self._standardize(self._sequence_array(values))
        loader = DataLoader(
            TensorDataset(torch.from_numpy(sequence)),
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
        )
        probabilities: list[np.ndarray] = []
        self.model_.eval()
        with torch.no_grad():
            for (batch_inputs,) in loader:
                probability_up = torch.sigmoid(self.model_(batch_inputs))
                probabilities.append(probability_up.cpu().numpy())
        probability_up = np.concatenate(probabilities).astype("float64", copy=False)
        return np.column_stack((1 - probability_up, probability_up))

    def diagnostics(self) -> dict[str, object]:
        parameter_count = (
            sum(parameter.numel() for parameter in self.model_.parameters())
            if self.model_ is not None
            else 0
        )
        return {
            "architecture": "two-layer causal dilated TCN with last/mean pooling",
            "sequence_length": self.sequence_length,
            "sequence_channels": list(self.channel_names),
            "hidden_channels": self.hidden_channels,
            "parameter_count": int(parameter_count),
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "training_loss": list(self.training_loss_),
            "normalization": "per-channel mean/std learned from training rows only",
        }


@dataclass
class CausalGRUClassifier:
    sequence_length: int
    hidden_channels: int
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    random_state: int
    channel_names: tuple[str, ...] = TCN_SEQUENCE_CHANNELS
    model_: _CausalGRU | None = field(default=None, init=False)
    channel_mean_: np.ndarray | None = field(default=None, init=False)
    channel_std_: np.ndarray | None = field(default=None, init=False)
    training_loss_: list[float] = field(default_factory=list, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"), init=False
    )

    def _ordered_columns(self) -> list[str]:
        return [
            f"tcn_{channel}_lag_{lag}"
            for lag in reversed(range(self.sequence_length))
            for channel in self.channel_names
        ]

    def _sequence_array(self, values: pd.DataFrame) -> np.ndarray:
        columns = self._ordered_columns()
        missing = sorted(set(columns) - set(values.columns))
        if missing:
            raise ValueError(
                "causal GRU input is missing sequence columns: " + ", ".join(missing)
            )
        array = values[columns].to_numpy(dtype="float32", copy=True)
        if not np.isfinite(array).all():
            raise ValueError("causal GRU sequence values must be finite")
        return array.reshape(
            len(values), self.sequence_length, len(self.channel_names)
        )

    def _standardize(self, sequence: np.ndarray) -> np.ndarray:
        if self.channel_mean_ is None or self.channel_std_ is None:
            raise ValueError("causal GRU standardization has not been fitted")
        standardized = (sequence - self.channel_mean_) / self.channel_std_
        return np.ascontiguousarray(standardized, dtype="float32")

    def fit(
        self,
        values: pd.DataFrame,
        labels: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> CausalGRUClassifier:
        if self.sequence_length <= 0 or self.hidden_channels <= 0:
            raise ValueError(
                "causal GRU sequence_length and hidden_channels must be positive"
            )
        if self.epochs <= 0 or self.batch_size <= 0:
            raise ValueError("causal GRU epochs and batch_size must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError(
                "causal GRU learning_rate must be positive and weight_decay non-negative"
            )
        target = np.asarray(labels, dtype="float32")
        if len(target) != len(values) or np.unique(target).size != 2:
            raise ValueError(
                "causal GRU target must align and contain both classes"
            )
        sequence = self._sequence_array(values)
        self.channel_mean_ = sequence.mean(axis=(0, 1), keepdims=True)
        channel_std = sequence.std(axis=(0, 1), keepdims=True)
        self.channel_std_ = np.maximum(channel_std, 1e-6)
        inputs = torch.from_numpy(self._standardize(sequence))
        targets = torch.from_numpy(target)
        if sample_weight is None:
            weights = torch.ones_like(targets)
        else:
            raw_weights = np.asarray(sample_weight, dtype="float32")
            if (
                raw_weights.shape != target.shape
                or not np.isfinite(raw_weights).all()
            ):
                raise ValueError(
                    "causal GRU sample weights must be finite and align with labels"
                )
            weights = torch.from_numpy(raw_weights)

        torch.manual_seed(self.random_state)
        generator = torch.Generator().manual_seed(self.random_state)
        self.model_ = _CausalGRU(len(self.channel_names), self.hidden_channels)
        optimizer = torch.optim.AdamW(
            self.model_.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        loss_function = nn.BCEWithLogitsLoss(reduction="none")
        loader = DataLoader(
            TensorDataset(inputs, targets, weights),
            batch_size=self.batch_size,
            shuffle=True,
            generator=generator,
            num_workers=0,
        )
        self.training_loss_.clear()
        self.model_.train()
        for _ in range(self.epochs):
            total_loss = 0.0
            total_weight = 0.0
            for batch_inputs, batch_targets, batch_weights in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model_(batch_inputs)
                individual_loss = loss_function(logits, batch_targets)
                loss = (individual_loss * batch_weights).sum() / batch_weights.sum()
                loss.backward()
                optimizer.step()
                total_loss += float((individual_loss.detach() * batch_weights).sum())
                total_weight += float(batch_weights.sum())
            self.training_loss_.append(total_loss / total_weight)
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("causal GRU model has not been fitted")
        sequence = self._standardize(self._sequence_array(values))
        loader = DataLoader(
            TensorDataset(torch.from_numpy(sequence)),
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
        )
        probabilities: list[np.ndarray] = []
        self.model_.eval()
        with torch.no_grad():
            for (batch_inputs,) in loader:
                probability_up = torch.sigmoid(self.model_(batch_inputs))
                probabilities.append(probability_up.cpu().numpy())
        probability_up = np.concatenate(probabilities).astype(
            "float64", copy=False
        )
        return np.column_stack((1 - probability_up, probability_up))

    def diagnostics(self) -> dict[str, object]:
        parameter_count = (
            sum(parameter.numel() for parameter in self.model_.parameters())
            if self.model_ is not None
            else 0
        )
        return {
            "architecture": "single-layer causal GRU with final-hidden pooling",
            "sequence_length": self.sequence_length,
            "sequence_channels": list(self.channel_names),
            "hidden_channels": self.hidden_channels,
            "parameter_count": int(parameter_count),
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "training_loss": list(self.training_loss_),
            "normalization": "per-channel mean/std learned from training rows only",
        }


@dataclass
class CausalTransformerClassifier:
    sequence_length: int
    model_dimension: int
    attention_heads: int
    encoder_layers: int
    feedforward_dimension: int
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    random_state: int
    channel_names: tuple[str, ...] = TCN_SEQUENCE_CHANNELS
    model_: _CausalTransformer | None = field(default=None, init=False)
    channel_mean_: np.ndarray | None = field(default=None, init=False)
    channel_std_: np.ndarray | None = field(default=None, init=False)
    training_loss_: list[float] = field(default_factory=list, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"), init=False
    )

    def _ordered_columns(self) -> list[str]:
        return [
            f"tcn_{channel}_lag_{lag}"
            for lag in reversed(range(self.sequence_length))
            for channel in self.channel_names
        ]

    def _sequence_array(self, values: pd.DataFrame) -> np.ndarray:
        columns = self._ordered_columns()
        missing = sorted(set(columns) - set(values.columns))
        if missing:
            raise ValueError(
                "causal Transformer input is missing sequence columns: "
                + ", ".join(missing)
            )
        array = values[columns].to_numpy(dtype="float32", copy=True)
        if not np.isfinite(array).all():
            raise ValueError("causal Transformer sequence values must be finite")
        return array.reshape(
            len(values), self.sequence_length, len(self.channel_names)
        )

    def _standardize(self, sequence: np.ndarray) -> np.ndarray:
        if self.channel_mean_ is None or self.channel_std_ is None:
            raise ValueError("causal Transformer standardization has not been fitted")
        standardized = (sequence - self.channel_mean_) / self.channel_std_
        return np.ascontiguousarray(standardized, dtype="float32")

    def fit(
        self,
        values: pd.DataFrame,
        labels: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> CausalTransformerClassifier:
        if self.sequence_length <= 0 or self.model_dimension <= 0:
            raise ValueError(
                "causal Transformer sequence_length and model_dimension must be positive"
            )
        if self.attention_heads <= 0 or self.model_dimension % self.attention_heads:
            raise ValueError(
                "causal Transformer heads must divide the model dimension"
            )
        if self.encoder_layers <= 0 or self.feedforward_dimension <= 0:
            raise ValueError(
                "causal Transformer layers and feedforward dimension must be positive"
            )
        if self.epochs <= 0 or self.batch_size <= 0:
            raise ValueError("causal Transformer epochs and batch_size must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError(
                "causal Transformer learning_rate must be positive and weight_decay non-negative"
            )
        target = np.asarray(labels, dtype="float32")
        if len(target) != len(values) or np.unique(target).size != 2:
            raise ValueError(
                "causal Transformer target must align and contain both classes"
            )
        sequence = self._sequence_array(values)
        self.channel_mean_ = sequence.mean(axis=(0, 1), keepdims=True)
        channel_std = sequence.std(axis=(0, 1), keepdims=True)
        self.channel_std_ = np.maximum(channel_std, 1e-6)
        inputs = torch.from_numpy(self._standardize(sequence))
        targets = torch.from_numpy(target)
        if sample_weight is None:
            weights = torch.ones_like(targets)
        else:
            raw_weights = np.asarray(sample_weight, dtype="float32")
            if raw_weights.shape != target.shape or not np.isfinite(raw_weights).all():
                raise ValueError(
                    "causal Transformer sample weights must be finite and align with labels"
                )
            weights = torch.from_numpy(raw_weights)

        torch.manual_seed(self.random_state)
        generator = torch.Generator().manual_seed(self.random_state)
        self.model_ = _CausalTransformer(
            input_channels=len(self.channel_names),
            sequence_length=self.sequence_length,
            model_dimension=self.model_dimension,
            attention_heads=self.attention_heads,
            encoder_layers=self.encoder_layers,
            feedforward_dimension=self.feedforward_dimension,
        )
        optimizer = torch.optim.AdamW(
            self.model_.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        loss_function = nn.BCEWithLogitsLoss(reduction="none")
        loader = DataLoader(
            TensorDataset(inputs, targets, weights),
            batch_size=self.batch_size,
            shuffle=True,
            generator=generator,
            num_workers=0,
        )
        self.training_loss_.clear()
        self.model_.train()
        for _ in range(self.epochs):
            total_loss = 0.0
            total_weight = 0.0
            for batch_inputs, batch_targets, batch_weights in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model_(batch_inputs)
                individual_loss = loss_function(logits, batch_targets)
                loss = (individual_loss * batch_weights).sum() / batch_weights.sum()
                loss.backward()
                optimizer.step()
                total_loss += float((individual_loss.detach() * batch_weights).sum())
                total_weight += float(batch_weights.sum())
            self.training_loss_.append(total_loss / total_weight)
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("causal Transformer model has not been fitted")
        sequence = self._standardize(self._sequence_array(values))
        loader = DataLoader(
            TensorDataset(torch.from_numpy(sequence)),
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
        )
        probabilities: list[np.ndarray] = []
        self.model_.eval()
        with torch.no_grad():
            for (batch_inputs,) in loader:
                probability_up = torch.sigmoid(self.model_(batch_inputs))
                probabilities.append(probability_up.cpu().numpy())
        probability_up = np.concatenate(probabilities).astype(
            "float64", copy=False
        )
        return np.column_stack((1 - probability_up, probability_up))

    def diagnostics(self) -> dict[str, object]:
        parameter_count = (
            sum(parameter.numel() for parameter in self.model_.parameters())
            if self.model_ is not None
            else 0
        )
        return {
            "architecture": "causal Transformer encoder with learned positions and last-token pooling",
            "sequence_length": self.sequence_length,
            "sequence_channels": list(self.channel_names),
            "model_dimension": self.model_dimension,
            "attention_heads": self.attention_heads,
            "encoder_layers": self.encoder_layers,
            "feedforward_dimension": self.feedforward_dimension,
            "dropout": 0.0,
            "parameter_count": int(parameter_count),
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "training_loss": list(self.training_loss_),
            "normalization": "per-channel mean/std learned from training rows only",
        }
