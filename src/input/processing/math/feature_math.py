from __future__ import annotations

from math import sqrt


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def percent_change(current: float, previous: float) -> float:
    return safe_divide(current - previous, abs(previous), 0.0)


def moving_average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def population_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = moving_average(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def z_score(value: float, values: list[float]) -> float:
    std = population_std(values)
    if std == 0:
        return 0.0
    return (value - moving_average(values)) / std
