#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Interface GTK 4/libadwaita do Monitor Tesouro."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from datetime import date, timedelta
from threading import Thread
from . import core


class MonitorWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Monitor Tesouro", default_width=1050, default_height=760)
        self.rows = []
        self.series = []
        self.period = 0
        self.set_default_size(1050, 760)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.refresh = Gtk.Button(label="Atualizar")
        self.refresh.add_css_class("suggested-action")
        self.refresh.connect("clicked", self.load_data)
        header.pack_end(self.refresh)
        toolbar.add_top_bar(header)
        clamp = Adw.Clamp(maximum_size=1100, tightening_threshold=800)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_top(24); page.set_margin_bottom(24)
        page.set_margin_start(24); page.set_margin_end(24)
        title = Gtk.Label(label="Tesouro IPCA+", xalign=0)
        title.add_css_class("title-1")
        page.append(title)
        self.subtitle = Gtk.Label(label="Histórico oficial de taxas desde 2002", xalign=0)
        self.subtitle.add_css_class("dim-label")
        page.append(self.subtitle)

        chartcard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        chartcard.add_css_class("card")
        chartcard.set_margin_top(8); chartcard.set_margin_bottom(8)
        charthead = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        charthead.set_margin_top(16); charthead.set_margin_start(16); charthead.set_margin_end(16)
        charthead.append(Gtk.Label(label="Evolução das taxas", xalign=0, hexpand=True))
        self.title_select = Gtk.DropDown.new_from_strings(["Carregando…"])
        self.title_select.connect("notify::selected", self.selection_changed)
        charthead.append(self.title_select)
        chartcard.append(charthead)
        periods = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        periods.set_margin_start(16); periods.set_margin_end(16)
        self.period_buttons = []
        for label, days in [("30 dias",30),("90 dias",90),("1 ano",365),("Tudo",0)]:
            button = Gtk.ToggleButton(label=label)
            button.set_active(days == 0)
            button.connect("toggled", self.period_changed, days)
            periods.append(button); self.period_buttons.append((button, days))
        chartcard.append(periods)
        self.chart = Gtk.DrawingArea()
        self.chart.set_content_height(360)
        self.chart.set_hexpand(True)
        self.chart.set_draw_func(self.draw_chart)
        self.chart.set_margin_start(12); self.chart.set_margin_end(12)
        chartcard.append(self.chart)
        self.chart_note = Gtk.Label(label="As taxas são fornecidas pelo Tesouro Transparente.", xalign=0)
        self.chart_note.add_css_class("dim-label")
        self.chart_note.set_margin_start(16); self.chart_note.set_margin_bottom(14)
        chartcard.append(self.chart_note)
        page.append(chartcard)

        self.latest = Gtk.Label(label="Taxas mais recentes", xalign=0)
        self.latest.add_css_class("title-3")
        page.append(self.latest)
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("boxed-list")
        page.append(self.listbox)
        self.status = Gtk.Label(label="Conectando ao Tesouro Transparente…", xalign=0)
        self.status.add_css_class("dim-label")
        page.append(self.status)
        clamp.set_child(page); toolbar.set_content(clamp); self.set_content(toolbar)
        self.load_data()

    def load_data(self, *_args):
        self.refresh.set_sensitive(False)
        self.status.set_text("Baixando histórico oficial…")
        def worker():
            try:
                cfg = core.carregar_config(core.PADRAO_CONFIG)
                url = cfg.get("fonte", {}).get("url", core.PADRAO_URL)
                raw = core.baixar(url, int(cfg.get("fonte", {}).get("timeout_segundos", 60)))
                rows = core.parse_csv(raw, somente_recente=False)
                GLib.idle_add(self.data_ready, rows, None)
            except Exception as exc:
                GLib.idle_add(self.data_ready, [], str(exc))
        Thread(target=worker, daemon=True).start()

    def data_ready(self, rows, error):
        self.refresh.set_sensitive(True)
        if error:
            self.status.set_text(f"Não foi possível atualizar: {error}")
            return
        self.rows = rows
        self.years = sorted({r["vencimento"].year for r in rows})
        self.title_select.set_model(Gtk.StringList.new([f"Tesouro IPCA+ · {y}" for y in self.years]))
        if self.years:
            self.title_select.set_selected(len(self.years)-1)
        recent = max(r["data_base"] for r in rows)
        self.status.set_text(f"{len(rows):,} observações históricas · dados até {recent:%d/%m/%Y}".replace(",", "."))
        self.render_latest()
        self.selection_changed()
        return GLib.SOURCE_REMOVE

    def render_latest(self):
        child = self.listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling(); self.listbox.remove(child); child = nxt
        latest = {}
        most_recent = max(x["data_base"] for x in self.rows)
        for r in self.rows:
            if r["data_base"] == most_recent:
                latest[r["vencimento"]] = r
        for maturity, row in sorted(latest.items()):
            line = Adw.ActionRow(title=f"Tesouro IPCA+ {maturity.year}",
                subtitle=f"Compra {row['taxa_compra_pct']:.3f}%  ·  Venda {row['taxa_venda_pct']:.3f}%")
            line.add_suffix(Gtk.Label(label=f"R$ {row['pu_compra']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.listbox.append(line)

    def selection_changed(self, *_args):
        if not self.rows or not self.years: return
        index = self.title_select.get_selected()
        if index >= len(self.years): return
        year = self.years[index]
        self.series = sorted((r for r in self.rows if r["vencimento"].year == year), key=lambda r:r["data_base"])
        self.chart.queue_draw()

    def period_changed(self, button, days):
        if button.get_active():
            self.period = days
            for other, other_days in self.period_buttons:
                if other_days != days: other.set_active(False)
            self.chart.queue_draw()

    def draw_chart(self, area, cr, width, height):
        style = self.get_style_context()
        fg = style.get_color()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.18)
        left, right, top, bottom = 58, width-18, 18, height-38
        points = self.series
        if self.period and points:
            cutoff = date.today() - timedelta(days=self.period)
            points = [p for p in points if p["data_base"] >= cutoff]
        if len(points) < 2:
            cr.set_source_rgb(fg.red, fg.green, fg.blue); cr.move_to(70, height/2)
            cr.show_text("Sem dados históricos suficientes para este período")
            return
        lo = min(min(p["taxa_compra_pct"],p["taxa_venda_pct"]) for p in points)
        hi = max(max(p["taxa_compra_pct"],p["taxa_venda_pct"]) for p in points)
        span = max(hi-lo, 0.1); lo -= span*.12; hi += span*.12
        first, last = points[0]["data_base"], points[-1]["data_base"]
        cr.set_line_width(1)
        for i in range(5):
            y = top + i*(bottom-top)/4
            cr.move_to(left,y); cr.line_to(right,y); cr.stroke()
            cr.set_source_rgba(fg.red,fg.green,fg.blue,.7)
            cr.move_to(4,y+4); cr.show_text(f"{hi-i*(hi-lo)/4:.2f}%")
            cr.set_source_rgba(fg.red,fg.green,fg.blue,.18)
        for key, color in [("taxa_compra_pct",(0.21,0.52,0.89)),("taxa_venda_pct",(0.20,0.63,0.42))]:
            cr.set_source_rgb(*color); cr.set_line_width(2)
            for i,p in enumerate(points):
                x=left+(p["data_base"]-first).days/max((last-first).days,1)*(right-left)
                y=bottom-(p[key]-lo)/(hi-lo)*(bottom-top)
                if i==0: cr.move_to(x,y)
                else: cr.line_to(x,y)
            cr.stroke()
        cr.set_source_rgba(fg.red,fg.green,fg.blue,.75)
        cr.move_to(left,bottom+22); cr.show_text(first.strftime("%d/%m/%Y"))
        cr.move_to(max(left,right-95),bottom+22); cr.show_text(last.strftime("%d/%m/%Y"))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="br.com.victorffrock.MonitorTesouro",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
    def do_activate(self):
        win = self.props.active_window or MonitorWindow(self)
        win.present()


def main():
    Adw.init()
    return App().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
