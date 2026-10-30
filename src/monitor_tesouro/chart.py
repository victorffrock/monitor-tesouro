#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Transformações puras usadas pelo gráfico e cobertas pela suíte de testes."""

from __future__ import annotations

from datetime import date, timedelta


RATE_KEYS = ("taxa_compra_pct", "taxa_venda_pct")


def maturity_dates(rows: list[dict]) -> list[date]:
    """Retorna vencimentos únicos em ordem cronológica."""
    return sorted({row["vencimento"] for row in rows})


def points_for_period(
    rows: list[dict],
    maturity: date,
    period_days: int,
    today: date | None = None,
) -> list[dict]:
    """Seleciona um título e limita datas quando o usuário escolhe um período."""
    points = [row for row in rows if row["vencimento"] == maturity]
    points.sort(key=lambda row: row["data_base"])
    if period_days == 0 or not points:
        return points
    reference = today or date.today()
    cutoff = reference - timedelta(days=period_days)
    return [point for point in points if point["data_base"] >= cutoff]


def rate_bounds(points: list[dict]) -> tuple[float, float] | None:
    """Calcula limites legíveis do eixo Y, incluindo margem para não cortar linhas."""
    if not points:
        return None
    low = min(point[key] for point in points for key in RATE_KEYS)
    high = max(point[key] for point in points for key in RATE_KEYS)
    span = high - low
    margin = max(span * 0.12, 0.08)
    return low - margin, high + margin


def point_coordinates(
    point: dict,
    first_day: date,
    last_day: date,
    low_rate: float,
    high_rate: float,
    bounds: tuple[float, float, float, float],
    rate_key: str,
) -> tuple[float, float]:
    """Converte data e taxa para coordenadas do desenho, sem depender de Cairo."""
    left, top, right, bottom = bounds
    total_days = max((last_day - first_day).days, 1)
    x = left + (point["data_base"] - first_day).days / total_days * (right - left)
    y = bottom - (point[rate_key] - low_rate) / (high_rate - low_rate) * (bottom - top)
    return x, y
