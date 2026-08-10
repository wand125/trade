from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


TRANSITION_STATE_COLUMNS = (
    "transition_current_direction",
    "transition_run_length_bucket",
    "transition_reversal_fraction_8",
    "transition_volatility_state_5_20",
)


@dataclass
class HierarchicalDirectionTransitionClassifier:
    """Estimate next-up probability from a fixed, causally observed bar state."""

    state_prior_strength: float = 64.0
    parent_prior_strength: float = 256.0
    probability_by_state_: np.ndarray | None = field(default=None, init=False)
    state_count_: np.ndarray | None = field(default=None, init=False)
    parent_probability_: np.ndarray | None = field(default=None, init=False)
    parent_count_: np.ndarray | None = field(default=None, init=False)
    global_probability_: float | None = field(default=None, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"), init=False
    )

    @staticmethod
    def _state_indices(values: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        missing = sorted(set(TRANSITION_STATE_COLUMNS) - set(values.columns))
        if missing:
            raise ValueError(
                "direction transition input is missing state columns: "
                + ", ".join(missing)
            )
        raw = values[list(TRANSITION_STATE_COLUMNS)].to_numpy(
            dtype="float64", copy=True
        )
        if not np.isfinite(raw).all():
            raise ValueError("direction transition state values must be finite")

        direction = raw[:, 0].astype("int64")
        run_length = raw[:, 1].astype("int64")
        reversal_bucket = np.digitize(raw[:, 2], (0.375, 0.625)).astype("int64")
        volatility_state = raw[:, 3].astype("int64")
        if not np.isin(direction, (-1, 0, 1)).all():
            raise ValueError("transition direction must be one of -1, 0, 1")
        if np.any((run_length < 0) | (run_length > 4)):
            raise ValueError("transition run length bucket must be within [0, 4]")
        if not np.isin(volatility_state, (-1, 0, 1)).all():
            raise ValueError("transition volatility state must be one of -1, 0, 1")
        if np.any((raw[:, 2] < 0) | (raw[:, 2] > 1)):
            raise ValueError("transition reversal fraction must be within [0, 1]")

        direction_index = direction + 1
        volatility_index = volatility_state + 1
        parent_index = direction_index * 3 + volatility_index
        state_index = (
            ((direction_index * 5 + run_length) * 3 + reversal_bucket) * 3
            + volatility_index
        )
        return state_index, parent_index

    def fit(
        self,
        values: pd.DataFrame,
        labels: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> HierarchicalDirectionTransitionClassifier:
        if self.state_prior_strength <= 0 or self.parent_prior_strength <= 0:
            raise ValueError("transition prior strengths must be positive")
        target = np.asarray(labels, dtype="int8")
        if len(target) != len(values) or not np.isin(target, (0, 1)).all():
            raise ValueError("transition target must align and be binary")
        if np.unique(target).size != 2:
            raise ValueError("transition target must contain both classes")
        if sample_weight is not None:
            weights = np.asarray(sample_weight, dtype="float64")
            if weights.shape != target.shape or not np.isfinite(weights).all():
                raise ValueError("transition sample weights must align and be finite")
            if not np.allclose(weights, weights[0]):
                raise ValueError(
                    "transition model supports only uniform sample weights"
                )

        state_index, parent_index = self._state_indices(values)
        self.global_probability_ = float(target.mean())
        self.parent_count_ = np.bincount(parent_index, minlength=9).astype("float64")
        parent_up = np.bincount(
            parent_index, weights=target, minlength=9
        ).astype("float64")
        self.parent_probability_ = (
            parent_up + self.parent_prior_strength * self.global_probability_
        ) / (self.parent_count_ + self.parent_prior_strength)

        self.state_count_ = np.bincount(state_index, minlength=135).astype("float64")
        state_up = np.bincount(
            state_index, weights=target, minlength=135
        ).astype("float64")
        state_parent = np.arange(135, dtype="int64")
        state_parent = (state_parent // 3 // 3 // 5) * 3 + state_parent % 3
        state_prior_probability = self.parent_probability_[state_parent]
        self.probability_by_state_ = (
            state_up + self.state_prior_strength * state_prior_probability
        ) / (self.state_count_ + self.state_prior_strength)
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.probability_by_state_ is None:
            raise ValueError("direction transition model has not been fitted")
        state_index, _ = self._state_indices(values)
        probability_up = self.probability_by_state_[state_index]
        return np.column_stack((1 - probability_up, probability_up))

    def diagnostics(self) -> dict[str, object]:
        if self.state_count_ is None or self.parent_count_ is None:
            raise ValueError("direction transition model has not been fitted")
        state_slots = np.arange(135, dtype="int64")
        direction_index = state_slots // 45
        run_length = (state_slots // 9) % 5
        reachable = ((direction_index == 1) & (run_length == 0)) | (
            (direction_index != 1) & (run_length >= 1)
        )
        reachable_counts = self.state_count_[reachable]
        return {
            "architecture": "hierarchical Bayesian direction-transition table",
            "state_definition": (
                "direction x capped run length x reversal-rate bucket x "
                "volatility state"
            ),
            "encoded_state_slots": 135,
            "structurally_reachable_states": int(reachable.sum()),
            "observed_states": int(np.count_nonzero(self.state_count_)),
            "unexpected_state_rows": float(self.state_count_[~reachable].sum()),
            "observed_parent_states": int(np.count_nonzero(self.parent_count_)),
            "state_prior_strength": self.state_prior_strength,
            "parent_prior_strength": self.parent_prior_strength,
            "global_probability_up": self.global_probability_,
            "minimum_reachable_state_rows": float(reachable_counts.min()),
            "median_reachable_state_rows": float(np.median(reachable_counts)),
            "maximum_reachable_state_rows": float(reachable_counts.max()),
        }
