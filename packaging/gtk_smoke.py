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

from monitor_tesouro.gui import MonitorApplication, MonitorWindow  # noqa: E402


def main() -> None:
    """Build the window, populate a real series, and execute Cairo drawing."""
    Adw.init()
    app = MonitorApplication()
    app.register()
    window = MonitorWindow(app, load_on_start=False)
    app.window = window
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
    assert app.lookup_action("about") is not None
    about = window.create_about_dialog()
    assert about.get_application_name() == "Monitor Tesouro"
    assert about.get_version() == "1.0.8"
    assert about.get_developer_name() == "Victor Ferreira Franco"
    assert list(about.get_developers()) == ["Victor Ferreira Franco"]
    assert about.get_website().endswith("monitor-tesouro")
    assert "inteligência artificial" in about.get_comments()
    assert about.get_issue_url().endswith("/issues")
    assert window.about_button.get_menu_model().get_n_items() == 1
    print("GTK window, About dialog, credits, links, and chart render verified.")


if __name__ == "__main__":
    main()
