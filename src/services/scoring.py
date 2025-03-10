import json
from typing import Dict


class ErrorScorer:
    def __init__(self):
        with open("config/error_weights.json") as f:
            self.weights = json.load(f)

    def calculate(self, state) -> float:
        base_score = 1.0
        error_counts = {}

        # First pass: count error frequencies
        for error in state.error_details:
            error_type = error["type"]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Second pass: apply weights
        for error_type, count in error_counts.items():
            severity = next(
                (e["severity"] for e in state.error_details if e["type"] == error_type),
                "medium",
            )

            # Base weight
            weight = self.weights.get(severity, {}).get(error_type, 0.3)

            # Domain adjustment
            domain_weight = (
                self.weights["domain_adj"]
                .get(state.problem_type, {})
                .get(error_type, 1.0)
            )

            # Repeat penalty
            repeat_penalty = 1 + (count - 1) * 0.15

            base_score -= weight * domain_weight * repeat_penalty

        # Confidence dampening
        return max(0, min(1, base_score * state.confidence_score))
