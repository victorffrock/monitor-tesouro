#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Interface gráfica do Monitor Tesouro (Tkinter, incluído no Python)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import core as monitor


APP = "Monitor Tesouro"
CONFIG = Path.home() / ".config/monitor-tesouro/config.toml"
DATA = Path.home() / ".local/share/monitor-tesouro"


class Janela(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("940x620")
        self.minsize(760, 500)
        self.configure(bg="#f4f7fb")
        self.config_data = self._config_inicial()
        self._montar()
        self._popular_config()
        self.after(250, self.atualizar)

    def _config_inicial(self):
        try:
            return monitor.carregar_config(CONFIG)
        except Exception:
            return {}

    def _montar(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f7fb")
        style.configure("TLabel", background="#f4f7fb", foreground="#17253a", font=("Sans", 10))
        style.configure("Title.TLabel", font=("Sans", 20, "bold"), foreground="#123a5a")
        style.configure("Sub.TLabel", foreground="#60758c")
        style.configure("Accent.TButton", font=("Sans", 10, "bold"), padding=(14, 9))
        style.configure("Treeview", rowheight=32, font=("Sans", 10), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Sans", 10, "bold"))

        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Tesouro IPCA+", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Taxas oficiais, patamares e alertas em um só lugar", style="Sub.TLabel").pack(anchor="w", pady=(3, 14))

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 12))
        self.status = tk.StringVar(value="Buscando taxas oficiais…")
        ttk.Label(bar, textvariable=self.status, style="Sub.TLabel").pack(side="left", fill="x", expand=True)
        self.refresh_btn = ttk.Button(bar, text="↻  Atualizar e verificar", style="Accent.TButton", command=self.atualizar)
        self.refresh_btn.pack(side="right", padx=(8, 0))

        cols = ("vencimento", "titulo", "compra", "venda", "pu", "base")
        self.tabela = ttk.Treeview(outer, columns=cols, show="headings", selectmode="browse")
        configs = [("vencimento", "Vencimento", 100, "center"), ("titulo", "Título", 310, "w"), ("compra", "Compra", 100, "e"), ("venda", "Venda", 100, "e"), ("pu", "PU compra", 120, "e"), ("base", "Data-base", 110, "center")]
        for c, t, w, a in configs:
            self.tabela.heading(c, text=t)
            self.tabela.column(c, width=w, anchor=a)
        self.tabela.pack(fill="both", expand=True)

        box = ttk.LabelFrame(outer, text="Configurações rápidas", padding=12)
        box.pack(fill="x", pady=(15, 0))
        ttk.Label(box, text="Patamares (%)").grid(row=0, column=0, sticky="w")
        self.limites = tk.StringVar()
        ttk.Entry(box, textvariable=self.limites, width=24).grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        self.desktop = tk.BooleanVar()
        ttk.Checkbutton(box, text="Notificação de desktop", variable=self.desktop).grid(row=0, column=1, sticky="w")
        self.email_on = tk.BooleanVar()
        ttk.Checkbutton(box, text="E-mail", variable=self.email_on).grid(row=1, column=1, sticky="w")
        self.daily = tk.BooleanVar()
        ttk.Checkbutton(box, text="Resumo diário", variable=self.daily).grid(row=2, column=1, sticky="w")
        self.email_user = tk.StringVar()
        self.email_to = tk.StringVar()
        self.email_password = tk.StringVar()
        ttk.Label(box, text="E-mail remetente").grid(row=0, column=2, sticky="w", padx=(12, 6))
        ttk.Entry(box, textvariable=self.email_user, width=23).grid(row=1, column=2, sticky="ew", padx=(12, 6))
        ttk.Label(box, text="Destinatário").grid(row=0, column=3, sticky="w", padx=(6, 6))
        ttk.Entry(box, textvariable=self.email_to, width=23).grid(row=1, column=3, sticky="ew", padx=(6, 6))
        ttk.Label(box, text="Senha de app").grid(row=0, column=4, sticky="w", padx=(6, 0))
        ttk.Entry(box, textvariable=self.email_password, width=21, show="•").grid(row=1, column=4, sticky="ew", padx=(6, 0))
        buttons = ttk.Frame(box)
        buttons.grid(row=3, column=2, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Salvar", command=self.salvar).pack(side="left")
        ttk.Button(buttons, text="Testar notificação", command=self.testar).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Instalar e agendar", command=self.agendar).pack(side="left", padx=(8, 0))
        box.columnconfigure(0, weight=1)
        box.columnconfigure(2, weight=1)
        box.columnconfigure(3, weight=1)
        box.columnconfigure(4, weight=1)
        footer = ttk.Label(outer, text="Dados do Tesouro Transparente · histórico local em ~/.local/share/monitor-tesouro", style="Sub.TLabel")
        footer.pack(anchor="w", pady=(12, 0))

    def _popular_config(self):
        c = self.config_data
        self.limites.set(", ".join(str(x) for x in c.get("alertas", {}).get("patamares_pct", [7, 8, 9, 10])))
        self.desktop.set(c.get("notificacoes", {}).get("desktop", {}).get("habilitado", True))
        self.email_on.set(c.get("notificacoes", {}).get("email", {}).get("habilitado", False))
        self.daily.set(c.get("resumo", {}).get("habilitado", False))
        mail = c.get("notificacoes", {}).get("email", {})
        self.email_user.set(mail.get("usuario", mail.get("remetente", "")))
        self.email_to.set(mail.get("destinatario", ""))

    def salvar(self):
        try:
            limites = sorted({float(x.strip()) for x in self.limites.get().split(",") if x.strip()})
            if not limites or any(x < 0 or x > 100 for x in limites):
                raise ValueError("Informe patamares entre 0 e 100, separados por vírgula.")
        except ValueError as e:
            messagebox.showerror("Configuração inválida", str(e))
            return False
        c = self.config_data
        fonte = c.get("fonte", {})
        armaz = c.get("armazenamento", {})
        n = c.get("notificacoes", {})
        desktop = n.get("desktop", {})
        email = dict(n.get("email", {}))
        email["usuario"] = self.email_user.get().strip()
        email["remetente"] = self.email_user.get().strip()
        email["destinatario"] = self.email_to.get().strip()
        resumo = c.get("resumo", {})
        toml = f'''# Configuração do Monitor Tesouro — pode ser editada nesta janela.\n\n[fonte]\nurl = {monitor.json.dumps(fonte.get("url", monitor.PADRAO_URL), ensure_ascii=False)}\ntimeout_segundos = {int(fonte.get("timeout_segundos", 45))}\n\n[armazenamento]\ndiretorio = {monitor.json.dumps(armaz.get("diretorio", "~/.local/share/monitor-tesouro"))}\n\n[alertas]\npatamares_pct = [{", ".join(str(x) for x in limites)}]\n\n[notificacoes.desktop]\nhabilitado = {str(self.desktop.get()).lower()}\ncomando = {monitor.json.dumps(desktop.get("comando", ["notify-send", "--app-name=Monitor Tesouro"]))}\n\n[notificacoes.email]\nhabilitado = {str(self.email_on.get()).lower()}\nservidor = {monitor.json.dumps(email.get("servidor", "smtp.gmail.com"))}\nporta = {int(email.get("porta", 587))}\nusuario = {monitor.json.dumps(email.get("usuario", ""))}\nremetente = {monitor.json.dumps(email.get("remetente", ""))}\ndestinatario = {monitor.json.dumps(email.get("destinatario", ""))}\nvariavel_senha = {monitor.json.dumps(email.get("variavel_senha", "TESOURO_SMTP_PASSWORD"))}\n'''
        toml += f'''\n[resumo]\nhabilitado = {str(self.daily.get()).lower()}\nvencimentos = {monitor.json.dumps(resumo.get("vencimentos", [2029, 2035, 2045]))}\n'''
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        email_secret = CONFIG.parent / "smtp-senha.txt"
        if self.email_password.get().strip():
            email_secret.write_text(self.email_password.get().strip().replace(" ", ""), encoding="utf-8")
            email_secret.chmod(0o600)
        if email_secret.exists():
            # Reabre TOML e insere a referência dentro da seção SMTP antes de [resumo].
            marcador = "\n[resumo]"
            toml = toml.replace(marcador, f"\narquivo_senha = {monitor.json.dumps(str(email_secret))}" + marcador)
        CONFIG.write_text(toml, encoding="utf-8")
        self.config_data = monitor.carregar_config(CONFIG)
        self.email_password.set("")
        self.status.set("Configurações salvas.")
        return True

    def atualizar(self):
        if str(self.refresh_btn["state"]) == "disabled":
            return
        self.refresh_btn.configure(state="disabled")
        self.status.set("Consultando CSV oficial e verificando cruzamentos…")
        threading.Thread(target=self._trabalho_atualizar, daemon=True).start()

    def _trabalho_atualizar(self):
        try:
            # A coleta e a detecção de alertas usam o mesmo fluxo do modo agendado.
            monitor.principal(["--config", str(CONFIG)])
            c = monitor.carregar_config(CONFIG)
            fonte = c.get("fonte", {})
            itens = monitor.parse_csv(monitor.baixar(fonte.get("url", monitor.PADRAO_URL), int(fonte.get("timeout_segundos", 45))))
            self.after(0, lambda: self._mostrar(itens))
        except Exception as exc:
            self.after(0, lambda e=str(exc): self._erro(e))

    def _mostrar(self, itens):
        self.tabela.delete(*self.tabela.get_children())
        for x in itens:
            self.tabela.insert("", "end", values=(x["vencimento"].strftime("%Y"), x["titulo"], f"{x['taxa_compra_pct']:.3f}%", f"{x['taxa_venda_pct']:.3f}%", f"R$ {x['pu_compra']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), x["data_base"].strftime("%d/%m/%Y")))
        base = itens[0]["data_base"].strftime("%d/%m/%Y")
        self.status.set(f"Atualizado · data-base {base} · {len(itens)} vencimentos")
        self.refresh_btn.configure(state="normal")

    def _erro(self, texto):
        self.status.set("Falha ao atualizar. Consulte os detalhes.")
        self.refresh_btn.configure(state="normal")
        messagebox.showerror("Não foi possível atualizar", texto)

    def testar(self):
        try:
            if not self.salvar():
                return
            log = monitor.configurar_log(DATA)
            monitor.notificar("Teste do Monitor Tesouro", "A interface e o canal de notificação estão funcionando.", self.config_data.get("notificacoes", {}), log)
            messagebox.showinfo("Teste enviado", "A solicitação de teste foi enviada aos canais habilitados. Se algum canal falhar, veja o log local.")
        except Exception as e:
            messagebox.showerror("Falha no teste", str(e))

    def agendar(self):
        if not self.salvar():
            return
        appimage = os.environ.get("APPIMAGE")
        if not appimage or not Path(appimage).exists():
            messagebox.showinfo("Agendamento", "O agendamento integrado fica disponível quando o app é executado como AppImage. Você pode usar a coleta manual por esta janela.")
            return
        try:
            dest = Path.home() / ".local/bin/Monitor-Tesouro.AppImage"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if Path(appimage).resolve() != dest.resolve():
                shutil.copy2(appimage, dest)
            dest.chmod(0o755)
            systemd = Path.home() / ".config/systemd/user"
            systemd.mkdir(parents=True, exist_ok=True)
            service = '''[Unit]\nDescription=Monitor de taxas do Tesouro IPCA+\nAfter=network-online.target\nWants=network-online.target\n[Service]\nType=oneshot\nExecStart=/usr/bin/env APPIMAGE_EXTRACT_AND_RUN=1 %h/.local/bin/Monitor-Tesouro.AppImage --background --config %h/.config/monitor-tesouro/config.toml\n'''
            timer = "[Unit]\nDescription=Executa o Monitor Tesouro em dias úteis às 18h30\n[Timer]\nOnCalendar=Mon..Fri *-*-* 18:30:00\nPersistent=true\nUnit=monitor-tesouro.service\n[Install]\nWantedBy=timers.target\n"
            (systemd / "monitor-tesouro.service").write_text(service, encoding="utf-8")
            (systemd / "monitor-tesouro.timer").write_text(timer, encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=15)
            subprocess.run(["systemctl", "--user", "enable", "--now", "monitor-tesouro.timer"], check=True, timeout=20)
            apps = Path.home() / ".local/share/applications"
            apps.mkdir(parents=True, exist_ok=True)
            desktop = '''[Desktop Entry]\nType=Application\nName=Monitor Tesouro\nComment=Monitor de taxas do Tesouro IPCA+\nExec=/usr/bin/env APPIMAGE_EXTRACT_AND_RUN=1 {dest}\nTerminal=false\nCategories=Finance;Utility;\n'''
            (apps / "monitor-tesouro.desktop").write_text(desktop, encoding="utf-8")
            messagebox.showinfo("Agendamento ativado", "O app foi instalado em ~/.local/bin e o timer de dias úteis às 18h30 foi ativado. A execução usa extração automática e não precisa de FUSE.")
        except Exception as e:
            messagebox.showerror("Não foi possível agendar", str(e))


def main():
    if "--background" in sys.argv:
        args = sys.argv[sys.argv.index("--background") + 1:]
        raise SystemExit(monitor.principal(args))
    Janela().mainloop()


if __name__ == "__main__":
    main()
