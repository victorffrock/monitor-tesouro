#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Interface gráfica do Monitor Tesouro (Tkinter, incluído no Python)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import core as monitor


APP = "Monitor Tesouro"
CONFIG = Path.home() / ".config/monitor-tesouro/config.toml"
DATA = Path.home() / ".local/share/monitor-tesouro"

FUNDO = "#f6f5f4"
CARTAO = "#ffffff"
TEXTO = "#241f31"
SECUNDARIO = "#5e5c64"
AZUL = "#3584e4"
VERDE = "#26a269"
GRADE = "#deddda"



class Janela(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("1080x820")
        self.minsize(820, 680)
        self.configure(bg=FUNDO)
        self.config_data = self._config_inicial()
        self.registros: list[dict] = []
        self.historico: dict[int, list[dict]] = {}
        self.anos: list[int] = []
        self.periodo_dias = tk.IntVar(value=90)
        self._montar()
        self.after(350, self.atualizar)

    def _config_inicial(self):
        try:
            return monitor.carregar_config(CONFIG)
        except (OSError, ValueError):
            return {}

    def _montar(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=FUNDO)
        style.configure("TLabel", background=FUNDO, foreground=TEXTO, font=("Cantarell", 10))
        style.configure("Title.TLabel", font=("Cantarell", 24, "bold"), foreground=TEXTO)
        style.configure("Subtitle.TLabel", font=("Cantarell", 11), foreground=SECUNDARIO)
        style.configure("Section.TLabel", font=("Cantarell", 14, "bold"), foreground=TEXTO)
        style.configure("Muted.TLabel", foreground=SECUNDARIO)
        style.configure("Card.TFrame", background=CARTAO, relief="solid", borderwidth=1)
        style.configure("Card.TLabel", background=CARTAO, foreground=TEXTO, font=("Cantarell", 10))
        style.configure("CardTitle.TLabel", background=CARTAO, foreground=TEXTO, font=("Cantarell", 14, "bold"))
        style.configure("CardMuted.TLabel", background=CARTAO, foreground=SECUNDARIO, font=("Cantarell", 10))
        style.configure("Accent.TButton", font=("Cantarell", 10, "bold"), padding=(14, 9))
        style.configure("Treeview", rowheight=34, font=("Cantarell", 10), background=CARTAO, fieldbackground=CARTAO)
        style.configure("Treeview.Heading", font=("Cantarell", 10, "bold"))

        outer = ttk.Frame(self, padding=(28, 24))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 20))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="Tesouro IPCA+", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Acompanhe as taxas e veja como elas mudam com o tempo.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="center")
        ttk.Button(actions, text="Preferências", command=self.abrir_preferencias).pack(side="left", padx=(0, 8))
        self.refresh_btn = ttk.Button(
            actions,
            text="Atualizar taxas",
            style="Accent.TButton",
            command=self.atualizar,
        )
        self.refresh_btn.pack(side="left")

        status_bar = ttk.Frame(outer)
        status_bar.pack(fill="x", pady=(0, 12))
        self.status = tk.StringVar(value="Preparando consulta às taxas oficiais…")
        ttk.Label(status_bar, textvariable=self.status, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        self.updated = tk.StringVar(value="")
        ttk.Label(status_bar, textvariable=self.updated, style="Muted.TLabel").pack(side="right")

        chart_card = ttk.Frame(outer, style="Card.TFrame", padding=18)
        chart_card.pack(fill="both", expand=True)
        chart_header = ttk.Frame(chart_card, style="Card.TFrame")
        chart_header.pack(fill="x", pady=(0, 12))
        chart_title = ttk.Frame(chart_header, style="Card.TFrame")
        chart_title.pack(side="left", fill="x", expand=True)
        ttk.Label(chart_title, text="Evolução das taxas", style="CardTitle.TLabel").pack(anchor="w")
        self.chart_summary = tk.StringVar(value="Taxas de compra e venda ao longo do tempo")
        ttk.Label(chart_title, textvariable=self.chart_summary, style="CardMuted.TLabel").pack(anchor="w", pady=(3, 0))

        chart_controls = ttk.Frame(chart_header, style="Card.TFrame")
        chart_controls.pack(side="right")
        self.year = tk.StringVar(value="")
        self.year_combo = ttk.Combobox(chart_controls, textvariable=self.year, state="readonly", width=15)
        self.year_combo.pack(side="right", padx=(8, 0))
        self.year_combo.bind("<<ComboboxSelected>>", lambda _event: self._desenhar_grafico())
        ttk.Label(chart_controls, text="Vencimento", style="CardMuted.TLabel").pack(side="right")

        period_row = ttk.Frame(chart_card, style="Card.TFrame")
        period_row.pack(fill="x", pady=(0, 8))
        ttk.Label(period_row, text="Período", style="CardMuted.TLabel").pack(side="left", padx=(0, 10))
        for label, days in (("30 dias", 30), ("90 dias", 90), ("1 ano", 365), ("Todo o histórico", 0)):
            ttk.Radiobutton(
                period_row,
                text=label,
                value=days,
                variable=self.periodo_dias,
                command=self._desenhar_grafico,
            ).pack(side="left", padx=(0, 8))

        legend = ttk.Frame(period_row, style="Card.TFrame")
        legend.pack(side="right")
        tk.Canvas(legend, width=12, height=12, bg=AZUL, highlightthickness=0).pack(side="left", padx=(12, 5))
        ttk.Label(legend, text="Compra", style="CardMuted.TLabel").pack(side="left")
        tk.Canvas(legend, width=12, height=12, bg=VERDE, highlightthickness=0).pack(side="left", padx=(14, 5))
        ttk.Label(legend, text="Venda", style="CardMuted.TLabel").pack(side="left")

        self.chart = tk.Canvas(chart_card, background=CARTAO, highlightthickness=0, height=370)
        self.chart.pack(fill="both", expand=True)
        self.chart.bind("<Configure>", lambda _event: self._desenhar_grafico())

        current = ttk.Frame(outer)
        current.pack(fill="both", expand=False, pady=(18, 0))
        current_header = ttk.Frame(current)
        current_header.pack(fill="x", pady=(0, 8))
        ttk.Label(current_header, text="Taxas mais recentes", style="Section.TLabel").pack(side="left")
        self.table_note = tk.StringVar(value="Selecione um vencimento para destacar no gráfico.")
        ttk.Label(current_header, textvariable=self.table_note, style="Muted.TLabel").pack(side="right")

        columns = ("vencimento", "compra", "venda", "pu", "data")
        self.tabela = ttk.Treeview(current, columns=columns, show="headings", height=5, selectmode="browse")
        for column, title, width, anchor in (
            ("vencimento", "Vencimento", 150, "w"),
            ("compra", "Taxa de compra", 170, "e"),
            ("venda", "Taxa de venda", 170, "e"),
            ("pu", "Preço unitário", 180, "e"),
            ("data", "Data-base", 150, "e"),
        ):
            self.tabela.heading(column, text=title)
            self.tabela.column(column, width=width, anchor=anchor)
        self.tabela.pack(fill="x")
        self.tabela.bind("<<TreeviewSelect>>", self._selecionar_linha)

        footer = ttk.Label(
            outer,
            text="Fonte: Tesouro Transparente  ·  O histórico fica salvo apenas neste computador.",
            style="Muted.TLabel",
        )
        footer.pack(anchor="w", pady=(12, 0))

    def atualizar(self):
        if str(self.refresh_btn["state"]) == "disabled":
            return
        self.refresh_btn.configure(state="disabled")
        self.status.set("Buscando taxas oficiais e atualizando o histórico…")
        self.updated.set("")
        threading.Thread(target=self._trabalho_atualizar, daemon=True).start()

    def _trabalho_atualizar(self):
        try:
            # O mesmo fluxo atualiza alertas e grava uma nova amostra no histórico local.
            monitor.principal(["--config", str(CONFIG)])
            config = monitor.carregar_config(CONFIG)
            fonte = config.get("fonte", {})
            registros = monitor.parse_csv(
                monitor.baixar(
                    fonte.get("url", monitor.PADRAO_URL),
                    int(fonte.get("timeout_segundos", 45)),
                )
            )
            pasta = Path(config.get("armazenamento", {}).get("diretorio", DATA)).expanduser()
            historico = monitor.carregar_historico(pasta / "historico.csv")
            self.after(0, lambda: self._mostrar(registros, historico))
        except Exception as erro:
            self.after(0, lambda texto=str(erro): self._erro(texto))

    def _mostrar(self, registros: list[dict], historico: dict[int, list[dict]]):
        self.registros = registros
        self.historico = historico
        self.tabela.delete(*self.tabela.get_children())
        for item in registros:
            ano = item["vencimento"].year
            self.tabela.insert(
                "",
                "end",
                iid=item["vencimento"].isoformat(),
                values=(
                    f"Tesouro IPCA+ {ano}",
                    self._percentual(item["taxa_compra_pct"]),
                    self._percentual(item["taxa_venda_pct"]),
                    f"R$ {item['pu_compra']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    item["data_base"].strftime("%d/%m/%Y"),
                ),
            )

        anos = sorted(set(historico) | {item["vencimento"].year for item in registros})
        self.anos = anos
        self.year_combo.configure(values=[f"{ano}" for ano in anos])
        if anos:
            selecionado = int(self.year.get()) if self.year.get().isdigit() else anos[0]
            if selecionado not in anos:
                selecionado = anos[0]
            self.year.set(str(selecionado))
        self._desenhar_grafico()

        base = max(item["data_base"] for item in registros)
        self.status.set(f"{len(registros)} vencimentos encontrados · data-base {base:%d/%m/%Y}")
        pontos = sum(len(serie) for serie in historico.values())
        self.updated.set(f"{pontos} observações no histórico")
        self.table_note.set("Clique em um vencimento para ver sua evolução.")
        self.refresh_btn.configure(state="normal")

    @staticmethod
    def _percentual(valor: float) -> str:
        return f"{valor:.3f}%".replace(".", ",")

    def _selecionar_linha(self, _event=None):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.year.set(str(date.fromisoformat(selecionados[0]).year))
        self._desenhar_grafico()

    def _desenhar_grafico(self):
        if not hasattr(self, "chart"):
            return
        canvas = self.chart
        canvas.delete("all")
        largura = max(canvas.winfo_width(), 520)
        altura = max(canvas.winfo_height(), 280)
        ano = int(self.year.get()) if self.year.get().isdigit() else None
        pontos = list(self.historico.get(ano, [])) if ano is not None else []
        if pontos and self.periodo_dias.get() > 0:
            limite = pontos[-1]["data_base"] - timedelta(days=self.periodo_dias.get())
            pontos = [ponto for ponto in pontos if ponto["data_base"] >= limite]

        if not pontos:
            if ano is not None and self.historico.get(ano):
                titulo = "Sem dados neste período"
                detalhe = "Escolha um intervalo maior para ver as observações anteriores."
                self.chart_summary.set("Nenhuma observação no intervalo selecionado")
            else:
                titulo = "Seu gráfico histórico começa com a primeira atualização."
                detalhe = "As taxas ficam guardadas neste computador e ganham forma com o tempo."
                self.chart_summary.set("Ainda não há observações para este vencimento")
            canvas.create_text(
                largura / 2,
                altura / 2 - 12,
                text=titulo,
                fill=TEXTO,
                font=("Cantarell", 13, "bold"),
            )
            canvas.create_text(
                largura / 2,
                altura / 2 + 16,
                text=detalhe,
                fill=SECUNDARIO,
                font=("Cantarell", 10),
            )
            return

        valores = [p[chave] for p in pontos for chave in ("taxa_compra_pct", "taxa_venda_pct")]
        minimo, maximo = min(valores), max(valores)
        amplitude = max(maximo - minimo, 0.4)
        minimo = max(0, minimo - amplitude * 0.15)
        maximo += amplitude * 0.15
        margem_esquerda, margem_direita, margem_topo, margem_baixo = 66, 22, 24, 44
        x0, x1 = margem_esquerda, largura - margem_direita
        y0, y1 = margem_topo, altura - margem_baixo

        def px(indice: int) -> float:
            if len(pontos) == 1:
                return (x0 + x1) / 2
            return x0 + (x1 - x0) * indice / (len(pontos) - 1)

        def py(valor: float) -> float:
            return y1 - (valor - minimo) * (y1 - y0) / (maximo - minimo)

        for passo in range(5):
            valor = minimo + (maximo - minimo) * passo / 4
            y = py(valor)
            canvas.create_line(x0, y, x1, y, fill=GRADE, dash=(2, 4))
            canvas.create_text(
                x0 - 10,
                y,
                text=f"{valor:.2f}%".replace(".", ","),
                anchor="e",
                fill=SECUNDARIO,
                font=("Cantarell", 9),
            )

        qtd_datas = min(5, len(pontos))
        indices = sorted({round(i * (len(pontos) - 1) / max(qtd_datas - 1, 1)) for i in range(qtd_datas)})
        for indice in indices:
            x = px(indice)
            canvas.create_text(
                x,
                y1 + 24,
                text=pontos[indice]["data_base"].strftime("%d/%m/%y"),
                fill=SECUNDARIO,
                font=("Cantarell", 9),
            )

        for chave, cor in (("taxa_compra_pct", AZUL), ("taxa_venda_pct", VERDE)):
            coordenadas = []
            for indice, ponto in enumerate(pontos):
                coordenadas.extend((px(indice), py(ponto[chave])))
            if len(coordenadas) >= 4:
                canvas.create_line(*coordenadas, fill=cor, width=2.5)
            for indice, ponto in enumerate(pontos):
                canvas.create_oval(
                    px(indice) - 3,
                    py(ponto[chave]) - 3,
                    px(indice) + 3,
                    py(ponto[chave]) + 3,
                    fill=cor,
                    outline=CARTAO,
                    width=1,
                )

        primeira = pontos[0]
        ultima = pontos[-1]
        variacao = f"{ultima['taxa_compra_pct'] - primeira['taxa_compra_pct']:+.3f}".replace(".", ",")
        self.chart_summary.set(
            f"Compra {self._percentual(ultima['taxa_compra_pct'])}  ·  "
            f"Venda {self._percentual(ultima['taxa_venda_pct'])}  ·  "
            f"variação da compra {variacao} p.p."
        )

    def _erro(self, texto: str):
        self.status.set("Não foi possível atualizar as taxas.")
        self.refresh_btn.configure(state="normal")
        messagebox.showerror("Falha ao atualizar", texto)

    def abrir_preferencias(self):
        janela = tk.Toplevel(self)
        janela.title("Preferências")
        janela.transient(self)
        janela.resizable(False, False)
        janela.configure(bg=FUNDO)
        janela.grab_set()

        quadro = ttk.Frame(janela, padding=22)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Alertas", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            quadro,
            text="Receba uma notificação quando a taxa de compra cruzar um destes patamares.",
            style="Subtitle.TLabel",
            wraplength=400,
        ).pack(anchor="w", pady=(5, 14))

        atual = self.config_data.get("alertas", {}).get("patamares_pct", [7, 8, 9, 10])
        limites = tk.StringVar(value=", ".join(str(valor) for valor in atual))
        ttk.Label(quadro, text="Patamares em porcentagem", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(quadro, textvariable=limites, width=42).pack(anchor="w", fill="x", pady=(5, 12))

        desktop = tk.BooleanVar(
            value=self.config_data.get("notificacoes", {}).get("desktop", {}).get("habilitado", True)
        )
        ttk.Checkbutton(quadro, text="Notificações na área de trabalho", variable=desktop).pack(anchor="w")

        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(20, 0))
        ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="right")
        ttk.Button(
            botoes,
            text="Salvar",
            style="Accent.TButton",
            command=lambda: self._salvar_preferencias(janela, limites.get(), desktop.get()),
        ).pack(side="right", padx=(0, 8))

    def _salvar_preferencias(self, janela: tk.Toplevel, valores: str, notificacoes: bool):
        try:
            limites = sorted({float(valor.strip()) for valor in valores.split(",") if valor.strip()})
            if not limites or any(valor < 0 or valor > 100 for valor in limites):
                raise ValueError("Use valores entre 0 e 100, separados por vírgula.")
        except ValueError as erro:
            messagebox.showerror("Patamar inválido", str(erro), parent=janela)
            return

        fonte = self.config_data.get("fonte", {})
        armazenamento = self.config_data.get("armazenamento", {})
        desktop = self.config_data.get("notificacoes", {}).get("desktop", {})
        resumo = self.config_data.get("resumo", {})
        toml = f"""# Preferências do Monitor Tesouro

[fonte]
url = {monitor.json.dumps(fonte.get("url", monitor.PADRAO_URL), ensure_ascii=False)}
timeout_segundos = {int(fonte.get("timeout_segundos", 45))}

[armazenamento]
diretorio = {monitor.json.dumps(armazenamento.get("diretorio", "~/.local/share/monitor-tesouro"))}

[alertas]
patamares_pct = [{", ".join(str(valor) for valor in limites)}]

[notificacoes.desktop]
habilitado = {str(notificacoes).lower()}
comando = {monitor.json.dumps(desktop.get("comando", ["notify-send", "--app-name=Monitor Tesouro"]))}

[resumo]
habilitado = {str(resumo.get("habilitado", False)).lower()}
vencimentos = {monitor.json.dumps(resumo.get("vencimentos", [2029, 2035, 2045]))}
"""
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(toml, encoding="utf-8")
        self.config_data = monitor.carregar_config(CONFIG)
        janela.destroy()
        self.status.set("Preferências salvas.")


def main():
    if "--background" in sys.argv:
        args = sys.argv[sys.argv.index("--background") + 1:]
        raise SystemExit(monitor.principal(args))
    Janela().mainloop()


if __name__ == "__main__":
    main()
