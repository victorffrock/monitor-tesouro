#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Janela principal do Monitor Tesouro em GTK 4 e libadwaita.

Esta camada cuida apenas da interface. A consulta/cache fica em data.py e as
transformações do gráfico ficam em chart.py, para que ambas possam ser testadas
sem iniciar uma janela.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from datetime import date  # noqa: E402
from threading import Thread  # noqa: E402

from . import chart, core, data  # noqa: E402


APP_ID = "br.com.victorffrock.MonitorTesouro"
APP_VERSION = "1.0.8"
PROJECT_URL = "https://github.com/victorffrock/monitor-tesouro"
COLOR_BUY = (0.16, 0.47, 0.84)
COLOR_SELL = (0.16, 0.57, 0.39)
PERIODS = (("30 dias", 30), ("90 dias", 90), ("1 ano", 365), ("Tudo", 0))


def _date_label(value: date) -> str:
    """Formata uma data-base no padrão mais familiar para usuários brasileiros."""
    return value.strftime("%d/%m/%Y")


class RateChart(Gtk.DrawingArea):
    """Desenha duas linhas de taxa com eixos, grade e datas de referência."""

    def __init__(self):
        super().__init__()
        self.points = []
        self.set_content_height(390)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_points(self, points: list[dict]) -> None:
        """Substitui a série exibida e agenda um redesenho."""
        self.points = points
        self.queue_draw()

    def _draw(self, _area, cr, width: int, height: int) -> None:
        """Renderiza grade, escalas, séries e mensagens vazias com Cairo."""
        context = self.get_style_context()
        foreground = context.get_color()
        left, top, right, bottom = 78, 20, max(width - 20, 100), max(height - 44, 80)
        points = self.points

        if not points:
            self._draw_message(cr, width, height, "Sem observações para este vencimento e período.", foreground)
            return

        limits = chart.rate_bounds(points)
        if limits is None:
            self._draw_message(cr, width, height, "Não há taxas válidas para desenhar.", foreground)
            return

        low, high = limits
        first_day = points[0]["data_base"]
        last_day = points[-1]["data_base"]
        plot_bounds = (left, top, right, bottom)

        # Eixo Y: cinco marcas mantêm a escala simples sem esconder diferenças.
        cr.set_font_size(11)
        cr.set_line_width(1)
        for tick in range(5):
            ratio = tick / 4
            y = top + ratio * (bottom - top)
            rate = high - ratio * (high - low)
            cr.set_source_rgba(foreground.red, foreground.green, foreground.blue, 0.18)
            cr.set_dash([2, 4], 0)
            cr.move_to(left, y)
            cr.line_to(right, y)
            cr.stroke()
            cr.set_dash([], 0)
            cr.set_source_rgba(foreground.red, foreground.green, foreground.blue, 0.82)
            cr.move_to(8, y + 4)
            cr.show_text(f"{rate:.2f}%".replace(".", ","))

        # As duas taxas usam a mesma escala para permitir comparação direta.
        for rate_key, color in (
            ("taxa_compra_pct", COLOR_BUY),
            ("taxa_venda_pct", COLOR_SELL),
        ):
            cr.set_source_rgb(*color)
            cr.set_line_width(2.5)
            cr.set_line_join(1)
            for index, point in enumerate(points):
                x, y = chart.point_coordinates(
                    point, first_day, last_day, low, high, plot_bounds, rate_key
                )
                if index == 0:
                    cr.move_to(x, y)
                else:
                    cr.line_to(x, y)
            cr.stroke()

        # Datas nas extremidades esclarecem o intervalo real da série.
        cr.set_source_rgba(foreground.red, foreground.green, foreground.blue, 0.82)
        cr.move_to(left, height - 12)
        cr.show_text(_date_label(first_day))
        right_text = _date_label(last_day)
        text_width = cr.text_extents(right_text).width
        cr.move_to(max(left, right - text_width), height - 12)
        cr.show_text(right_text)

    @staticmethod
    def _draw_message(cr, width: int, height: int, message: str, foreground) -> None:
        """Mostra um estado vazio legível em vez de deixar o gráfico em branco."""
        cr.set_source_rgba(foreground.red, foreground.green, foreground.blue, 0.78)
        cr.set_font_size(14)
        extents = cr.text_extents(message)
        cr.move_to(max((width - extents.width) / 2, 12), height / 2)
        cr.show_text(message)


class MonitorWindow(Adw.ApplicationWindow):
    """Composição principal da aplicação e ligação entre controles e dados."""

    def __init__(self, application, load_on_start: bool = True):
        super().__init__(application=application, title="Monitor Tesouro")
        self.set_default_size(1050, 820)
        self.set_size_request(720, 620)
        self.rows: list[dict] = []
        self.maturities: list[date] = []
        self.selected_maturity: date | None = None
        self.period_days = 0

        self._build_window()
        if load_on_start:
            self.refresh_history()

    def _build_window(self) -> None:
        """Monta a hierarquia visual usando componentes GTK e Adwaita."""
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Atualizar histórico")
        self.refresh_button.add_css_class("suggested-action")
        self.refresh_button.connect("clicked", self.refresh_history)
        header.pack_end(self.refresh_button)

        # O menu principal contém as informações institucionais do aplicativo.
        self.about_button = Gtk.MenuButton()
        self.about_button.set_icon_name("open-menu-symbolic")
        self.about_button.set_tooltip_text("Menu")
        menu = Gio.Menu()
        menu.append("Sobre o Monitor Tesouro", "app.about")
        self.about_button.set_menu_model(menu)
        header.pack_end(self.about_button)
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(maximum_size=1100, tightening_threshold=820)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_top(28)
        page.set_margin_bottom(28)
        page.set_margin_start(24)
        page.set_margin_end(24)

        # A introdução explica o conteúdo antes dos controles do gráfico.
        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label="Tesouro IPCA+", xalign=0)
        title.add_css_class("title-1")
        intro.append(title)
        description = Gtk.Label(
            label="Acompanhe a evolução das taxas dos títulos públicos.",
            xalign=0,
            wrap=True,
        )
        description.add_css_class("dim-label")
        intro.append(description)
        page.append(intro)

        # O status distingue atualização, cache offline e erros de conexão.
        self.status = Gtk.Label(label="Preparando o histórico…", xalign=0)
        self.status.add_css_class("dim-label")
        self.status.set_wrap(True)
        page.append(self.status)

        page.append(self._build_chart_card())
        page.append(self._build_rates_section())

        clamp.set_child(page)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(clamp)
        toolbar.set_content(scroller)
        self.set_content(toolbar)

    def _build_chart_card(self) -> Gtk.Widget:
        """Agrupa seletor, período, legenda e canvas em um cartão único."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("card")
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(1)
        card.set_margin_end(1)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top_row.set_margin_top(18)
        top_row.set_margin_start(18)
        top_row.set_margin_end(18)
        heading = Gtk.Label(label="Evolução das taxas", xalign=0, hexpand=True)
        heading.add_css_class("title-3")
        top_row.append(heading)
        self.maturity_picker = Gtk.DropDown.new_from_strings(["Carregando…"])
        self.maturity_picker.set_tooltip_text("Escolha o vencimento do título")
        self.maturity_picker.connect("notify::selected", self._on_maturity_changed)
        top_row.append(self.maturity_picker)
        card.append(top_row)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        controls.add_css_class("linked")
        controls.set_margin_start(18)
        controls.set_margin_end(18)
        self.period_buttons = []
        for index, (label, days) in enumerate(PERIODS):
            button = Gtk.ToggleButton(label=label)
            if index:
                button.set_group(self.period_buttons[0])
            button.connect("toggled", self._on_period_changed, days)
            controls.append(button)
            self.period_buttons.append(button)
        self.period_buttons[-1].set_active(True)
        card.append(controls)

        self.chart = RateChart()
        self.chart.set_margin_start(12)
        self.chart.set_margin_end(12)
        card.append(self.chart)
        card.append(self._build_legend())
        return card

    @staticmethod
    def _build_legend() -> Gtk.Widget:
        """Apresenta as duas séries com os mesmos nomes usados na lista de taxas."""
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        legend.set_halign(Gtk.Align.CENTER)
        legend.set_margin_bottom(18)
        for title, color in (("Compra", COLOR_BUY), ("Venda", COLOR_SELL)):
            swatch = Gtk.DrawingArea()
            swatch.set_content_width(12)
            swatch.set_content_height(12)
            swatch.set_draw_func(
                lambda _area, cr, _w, _h, rgb=color: (
                    cr.set_source_rgb(*rgb),
                    cr.arc(6, 6, 5, 0, 6.28318),
                    cr.fill(),
                )
            )
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            item.append(swatch)
            item.append(Gtk.Label(label=title))
            legend.append(item)
        return legend

    def _build_rates_section(self) -> Gtk.Widget:
        """Cria uma lista acessível de taxas atuais que também seleciona o gráfico."""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        heading = Gtk.Label(label="Taxas mais recentes", xalign=0, hexpand=True)
        heading.add_css_class("title-3")
        heading_row.append(heading)
        self.latest_label = Gtk.Label(label="", xalign=1)
        self.latest_label.add_css_class("dim-label")
        heading_row.append(self.latest_label)
        section.append(heading_row)

        self.rates_list = Gtk.ListBox()
        self.rates_list.add_css_class("boxed-list")
        self.rates_list.set_selection_mode(Gtk.SelectionMode.NONE)
        section.append(self.rates_list)
        return section

    @staticmethod
    def _destroy_children(container: Gtk.Widget) -> None:
        """Remove linhas antigas antes de preencher as taxas da data mais nova."""
        child = container.get_first_child()
        while child:
            following = child.get_next_sibling()
            container.remove(child)
            child = following

    def create_about_dialog(self) -> Adw.AboutDialog:
        """Cria o diálogo padrão do GNOME com créditos, documentação e links."""
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Monitor Tesouro")
        dialog.set_application_icon(APP_ID)
        dialog.set_version(APP_VERSION)
        dialog.set_developer_name("Victor Ferreira Franco")
        dialog.set_developers(["Victor Ferreira Franco"])
        dialog.set_comments(
            "Monitor de taxas e histórico dos títulos Tesouro IPCA+. "
            "Desenvolvido por Victor Ferreira Franco, com assistência de "
            "inteligência artificial (OpenAI Codex)."
        )
        dialog.set_copyright("© 2026 Victor Ferreira Franco")
        dialog.set_license("GPL-3.0-only")
        dialog.set_website(PROJECT_URL)
        dialog.set_issue_url(f"{PROJECT_URL}/issues")
        dialog.add_link("Documentação", f"{PROJECT_URL}#readme")
        dialog.add_link("Código-fonte", PROJECT_URL)
        dialog.add_credit_section("Assistência de IA", ["OpenAI Codex"])
        return dialog

    def refresh_history(self, *_args) -> None:
        """Atualiza em segundo plano sem bloquear a janela."""
        self.refresh_button.set_sensitive(False)
        self.status.set_text("Buscando o histórico oficial…")

        def worker():
            try:
                config = core.carregar_config(core.PADRAO_CONFIG)
                source = config.get("fonte", {})
                rows, message = data.get_history(
                    url=source.get("url", core.PADRAO_URL),
                    timeout=int(source.get("timeout_segundos", 60)),
                )
                GLib.idle_add(self._apply_history, rows, message, None)
            except Exception as error:
                GLib.idle_add(self._apply_history, [], "", str(error))

        Thread(target=worker, name="tesouro-history-refresh", daemon=True).start()

    def _apply_history(self, rows: list[dict], message: str, error: str | None) -> bool:
        """Atualiza os controles na thread GTK após terminar a leitura de dados."""
        self.refresh_button.set_sensitive(True)
        if error:
            self.status.set_text(f"Não foi possível carregar o histórico: {error}")
            self.chart.set_points([])
            return GLib.SOURCE_REMOVE

        self.rows = rows
        self.maturities = chart.maturity_dates(rows)
        if self.maturities:
            labels = [
                f"Tesouro IPCA+ · {maturity:%Y} ({maturity:%d/%m})"
                for maturity in self.maturities
            ]
            self.maturity_picker.set_model(Gtk.StringList.new(labels))
            if self.selected_maturity not in self.maturities:
                self.selected_maturity = self.maturities[-1]
            self.maturity_picker.set_selected(self.maturities.index(self.selected_maturity))
            self._render_latest_rates()
        else:
            self.chart.set_points([])
            self._destroy_children(self.rates_list)
            self.status.set_text(message or "Ainda não há observações no histórico.")
            return GLib.SOURCE_REMOVE

        latest_date = max(row["data_base"] for row in rows)
        self.latest_label.set_text(f"Data-base {_date_label(latest_date)}")
        self.status.set_text(
            f"{len(rows):,} observações disponíveis · {_date_label(latest_date)}".replace(",", ".")
            + f" · {message}"
        )
        self._update_chart()
        return GLib.SOURCE_REMOVE

    def _render_latest_rates(self) -> None:
        """Mostra a última cotação encontrada para cada vencimento."""
        self._destroy_children(self.rates_list)
        if not self.rows:
            return
        latest_date = max(row["data_base"] for row in self.rows)
        latest_rows = [
            row for row in self.rows if row["data_base"] == latest_date
        ]
        for row in sorted(latest_rows, key=lambda item: item["vencimento"]):
            maturity = row["vencimento"]
            action = Adw.ActionRow(
                title=f"Tesouro IPCA+ · {maturity:%Y}",
                subtitle=(
                    f"Compra {data.format_rate(row['taxa_compra_pct'])}"
                    f"   ·   Venda {data.format_rate(row['taxa_venda_pct'])}"
                ),
            )
            action.add_suffix(Gtk.Label(label=data.format_currency(row["pu_compra"])))
            action.set_activatable(True)
            action.connect("activated", self._select_maturity, maturity)
            self.rates_list.append(action)

    def _select_maturity(self, _row, maturity: date) -> None:
        """Selecionar uma taxa na lista move o gráfico para aquele vencimento."""
        self.selected_maturity = maturity
        self.maturity_picker.set_selected(self.maturities.index(maturity))
        self._update_chart()

    def _on_maturity_changed(self, picker, _property) -> None:
        """Atualiza a série sempre que o usuário escolhe outro título."""
        index = picker.get_selected()
        if index < len(self.maturities):
            self.selected_maturity = self.maturities[index]
            self._update_chart()

    def _on_period_changed(self, button, days: int) -> None:
        """Mantém um período sempre ativo e aplica a escolha ao gráfico."""
        if not button.get_active():
            button.set_active(True)
            return
        self.period_days = days
        self._update_chart()

    def _update_chart(self) -> None:
        """Prepara pontos para o vencimento e intervalo selecionados."""
        if self.selected_maturity is None:
            self.chart.set_points([])
            return
        points = chart.points_for_period(
            self.rows, self.selected_maturity, self.period_days
        )
        self.chart.set_points(points)


class MonitorApplication(Adw.Application):
    """Aplicação GTK que cria uma única janela principal."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._show_about_dialog)
        self.add_action(about_action)

    def _show_about_dialog(self, *_args) -> None:
        """Apresenta o diálogo libadwaita associado à janela ativa."""
        if self.window is None:
            self.do_activate()
        self.window.create_about_dialog().present(self.window)

    def do_activate(self):
        if self.window is None:
            self.window = MonitorWindow(self)
        self.window.present()


def main() -> int:
    """Ponto de entrada usado pelo AppImage e pelo modo código-fonte."""
    Adw.init()
    return MonitorApplication().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
