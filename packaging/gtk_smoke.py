#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Smoke test that creates the real GTK window and renders a populated chart.

Run with system GTK bindings or the equivalent runtime inside the built AppImage:
    xvfb-run -a python3 packaging/gtk_smoke.py
"""

from datetime import date

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from monitor_tesouro.gui import APP_ID, MonitorWindow  # noqa: E402


def main() -> None:
    """Build the window, populate a real series, and execute Cairo drawing."""
    Adw.init()
    app = Adw.Application(application_id=APP_ID)
    app.register()
    window = MonitorWindow(app, load_on_start=False)
    maturity = date(2035, 5, 15)
    points = [
        {
            "data_base": date(2024, 1, 10),
            "vencimento": maturity,
            "taxa_compra_pct": 5.2,
            "taxa_venda_pct": 5.4,
            "pu_compra": 1000.0,
            "pu_venda": 990.0,
        },
        {
            "data_base": date(2024, 2, 10),
            "vencimento": maturity,
            "taxa_compra_pct": 5.8,
            "taxa_venda_pct": 6.0,
            "pu_compra": 1010.0,
            "pu_venda": 1000.0,
        },
    ]
    window._apply_history(points, "Dados de demonstração para o smoke test.", None)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1000, 420)
    context = cairo.Context(surface)
    window.chart._draw(window.chart, context, 1000, 420)
    surface.flush()
    assert len(window.chart.points) == 2
    assert Gtk.get_major_version() == 4
    print("GTK window instantiated; two-point purchase/sale chart rendered.")


if __name__ == "__main__":
    main()
