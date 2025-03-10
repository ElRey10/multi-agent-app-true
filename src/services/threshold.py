class ThresholdCalculator:
    def __init__(self, base_threshold: float = 0.7):
        self.base = base_threshold

    def dynamic_threshold(self, state) -> float:
        factors = {
            "critical_errors": sum(
                1 for e in state.error_details if e["severity"] == "critical"
            ),
            "complexity": len(state.config["constraints"]) / 10,
            "trend": self._calculate_trend(state.error_history),
        }

        adjustments = (
            (factors["critical_errors"] * 0.1)
            + (factors["complexity"] * 0.05)
            + (factors["trend"] * 0.2)
        )

        return min(0.9, max(0.4, self.base + adjustments))

    def _calculate_trend(self, history: list) -> float:
        if len(history) < 2:
            return 0
        return (history[-1] - history[0]) / len(history)
