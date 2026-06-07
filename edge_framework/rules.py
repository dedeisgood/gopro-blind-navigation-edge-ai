from __future__ import annotations

import operator
from collections import Counter

from .config import RuleConfig
from .types import Detection, Event, Frame


OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "<=": operator.le,
    "<": operator.lt,
}


class RuleEngine:
    def __init__(self, rules: list[RuleConfig]) -> None:
        self.rules = rules

    def evaluate(self, frame: Frame, detections: list[Detection]) -> list[Event]:
        events: list[Event] = []
        counts = Counter(detection.class_name for detection in detections)

        for rule in self.rules:
            if rule.type == "class_count":
                event = self._evaluate_class_count(rule, frame, counts)
                if event is not None:
                    events.append(event)
                continue

            raise ValueError(f"Unsupported rule type: {rule.type}")

        return events

    def _evaluate_class_count(self, rule: RuleConfig, frame: Frame, counts: Counter[str]) -> Event | None:
        class_name = rule.params["class_name"]
        threshold = int(rule.params["threshold"])
        operator_name = rule.params.get("operator", ">=")
        compare = OPERATORS[operator_name]
        actual = counts[class_name]

        if not compare(actual, threshold):
            return None

        return Event(
            rule_name=rule.name,
            frame_index=frame.index,
            timestamp_s=frame.timestamp_s,
            message=f"{class_name} count {actual} {operator_name} {threshold}",
            payload={
                "class_name": class_name,
                "actual": actual,
                "operator": operator_name,
                "threshold": threshold,
            },
        )

