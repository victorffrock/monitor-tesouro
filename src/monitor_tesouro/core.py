#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Monitor local das taxas do Tesouro IPCA+ usando somente a biblioteca padrão."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import smtplib
import ssl
import subprocess
import sys
import tomllib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from urllib.error import URLError
from urllib.request import Request, urlopen


PADRAO_URL = "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
PADRAO_CONFIG = Path.home() / ".config/monitor-tesouro/config.toml"
PADRAO_DIR = Path.home() / ".local/share/monitor-tesouro"
HIST_CABECALHO = ["data_execucao", "data_base", "vencimento", "titulo", "taxa_compra_pct", "taxa_venda_pct", "pu_compra", "pu_venda"]


def norm(s: str) -> str:
    """Normaliza cabeçalhos para reconhecer variações simples do portal."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s.strip().lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s)


def numero(valor: str) -> float | None:
    valor = (valor or "").strip().replace("%", "")
    if not valor:
        return None
    # O arquivo oficial usa vírgula decimal e ponto de milhar.
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def data_br(valor: str) -> date:
    return datetime.strptime(valor.strip(), "%d/%m/%Y").date()


def achar(cabecalhos: dict[str, str], *opcoes: str) -> str | None:
    for opcao in opcoes:
        if norm(opcao) in cabecalhos:
            return cabecalhos[norm(opcao)]
    return None


def parse_csv(conteudo: bytes) -> list[dict]:
    """Lê o CSV oficial, seleciona IPCA+ sem cupom e devolve só a data-base mais recente."""
    texto = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ValueError("Não foi possível decodificar CSV em UTF-8 ou Latin-1")
    leitor = csv.DictReader(texto.splitlines(), delimiter=";")
    if not leitor.fieldnames:
        raise ValueError("CSV sem cabeçalho")
    campos = {norm(c): c for c in leitor.fieldnames if c}
    tipo = achar(campos, "Tipo Titulo", "Titulo")
    venc = achar(campos, "Data Vencimento", "Vencimento")
    base = achar(campos, "Data Base", "Data Referencia")
    compra = achar(campos, "Taxa Compra Manha", "Taxa Compra")
    venda = achar(campos, "Taxa Venda Manha", "Taxa Venda")
    pu_compra = achar(campos, "PU Compra Manha", "PU Compra")
    pu_venda = achar(campos, "PU Venda Manha", "PU Venda")
    faltando = [n for n, c in (("tipo/título", tipo), ("vencimento", venc), ("data-base", base), ("taxa compra", compra), ("taxa venda", venda), ("PU compra", pu_compra), ("PU venda", pu_venda)) if c is None]
    if faltando:
        raise ValueError("Cabeçalhos esperados não encontrados: " + ", ".join(faltando) + "; encontrados: " + ", ".join(leitor.fieldnames))

    linhas = []
    for row in leitor:
        nome = (row.get(tipo) or "").strip()
        nome_norm = norm(nome)
        if "ipca" not in nome_norm or "semestrais" in nome_norm or "comjuros" in nome_norm:
            continue
        try:
            dt = data_br(row.get(base, ""))
            dv = data_br(row.get(venc, ""))
        except ValueError:
            continue
        tc, tv = numero(row.get(compra, "")), numero(row.get(venda, ""))
        pc, pv = numero(row.get(pu_compra, "")), numero(row.get(pu_venda, ""))
        if None in (tc, tv, pc, pv):
            continue
        linhas.append({"data_base": dt, "vencimento": dv, "titulo": nome, "taxa_compra_pct": tc, "taxa_venda_pct": tv, "pu_compra": pc, "pu_venda": pv})
    if not linhas:
        raise ValueError("Nenhuma linha IPCA+ principal válida encontrada; confira o layout e os nomes dos títulos")
    mais_recente = max(x["data_base"] for x in linhas)
    # Duplicatas eventuais para o mesmo vencimento são reduzidas à última ocorrência do CSV.
    saida = {}
    for x in linhas:
        if x["data_base"] == mais_recente:
            saida[x["vencimento"]] = x
    return [saida[k] for k in sorted(saida)]


def cruzamentos(anterior: float, atual: float, patamares: list[float]) -> list[tuple[float, str]]:
    eventos = []
    for p in patamares:
        if anterior < p <= atual:
            eventos.append((p, "alta"))
        elif anterior > p >= atual:
            eventos.append((p, "queda"))
    return eventos


def carregar_config(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    with caminho.open("rb") as f:
        return tomllib.load(f)


def configurar_log(pasta: Path, somente_console: bool = False) -> logging.Logger:
    log = logging.getLogger("monitor_tesouro")
    log.setLevel(logging.INFO)
    if not log.handlers:
        if not somente_console:
            pasta.mkdir(parents=True, exist_ok=True)
            h = RotatingFileHandler(pasta / "log.txt", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(h)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        log.addHandler(console)
    return log


def baixar(url: str, timeout: int) -> bytes:
    req = Request(url, headers={"User-Agent": "monitor-tesouro/1.0 (uso pessoal)"})
    with urlopen(req, timeout=timeout) as resp:
        tipo = resp.headers.get("Content-Type", "")
        dados = resp.read()
    if not dados or b"<html" in dados[:500].lower():
        raise ValueError("A URL não retornou um CSV; verifique o endereço no Tesouro Transparente")
    return dados


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return padrao


def salvar_json(caminho: Path, dado) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dado, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def gravar_historico(caminho: Path, linhas: list[dict], hoje: date) -> None:
    existentes = set()
    if caminho.exists():
        with caminho.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existentes.add((r.get("data_base"), r.get("vencimento")))
    novo = []
    for x in linhas:
        chave = (x["data_base"].isoformat(), x["vencimento"].isoformat())
        if chave not in existentes:
            novo.append([hoje.isoformat(), chave[0], chave[1], x["titulo"], x["taxa_compra_pct"], x["taxa_venda_pct"], x["pu_compra"], x["pu_venda"]])
            existentes.add(chave)
    with caminho.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if caminho.stat().st_size == 0:
            w.writerow(HIST_CABECALHO)
        w.writerows(novo)


def notificar(titulo: str, corpo: str, cfg: dict, log: logging.Logger) -> None:
    desktop = cfg.get("desktop", {})
    if desktop.get("habilitado", True):
        comando = desktop.get("comando", ["notify-send", "--app-name=Monitor Tesouro"])
        try:
            subprocess.run([*comando, titulo, corpo], check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except (OSError, subprocess.SubprocessError) as e:
            log.error("Notificação desktop falhou: %s", e)
    email_cfg = cfg.get("email", {})
    if email_cfg.get("habilitado", False):
        try:
            senha = os.environ.get(email_cfg.get("variavel_senha", "TESOURO_SMTP_PASSWORD"), "")
            arquivo_senha = email_cfg.get("arquivo_senha")
            if not senha and arquivo_senha:
                p = Path(arquivo_senha).expanduser()
                if p.stat().st_mode & 0o077:
                    raise PermissionError(f"Permissões inseguras em {p}; use chmod 600")
                senha = p.read_text(encoding="utf-8").strip()
            if not senha:
                raise ValueError("Senha SMTP não definida")
            msg = EmailMessage()
            msg["Subject"] = titulo
            msg["From"] = email_cfg["remetente"]
            msg["To"] = email_cfg["destinatario"]
            msg.set_content(corpo)
            host, porta = email_cfg.get("servidor", "smtp.gmail.com"), int(email_cfg.get("porta", 587))
            with smtplib.SMTP(host, porta, timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(email_cfg.get("usuario", email_cfg["remetente"]), senha)
                smtp.send_message(msg)
        except Exception as e:
            log.error("E-mail falhou: %s", e)


def resumo(linhas: list[dict], historico: Path, cfg: dict) -> str:
    anos = cfg.get("resumo", {}).get("vencimentos", [2029, 2035, 2045])
    por_ano = {x["vencimento"].year: x for x in linhas}
    hist = {}
    if historico.exists():
        with historico.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                hist.setdefault((int(r["vencimento"][:4]), r["data_base"]), float(r["taxa_compra_pct"]))
    hoje_base = max(x["data_base"] for x in linhas)
    partes = [f"Resumo Tesouro IPCA+ — data-base {hoje_base.strftime('%d/%m/%Y')}:"]
    for ano in anos:
        x = por_ano.get(int(ano))
        if not x:
            partes.append(f"{ano}: sem título disponível.")
            continue
        extra = []
        for dias in (7, 30):
            alvo = (hoje_base - timedelta(days=dias)).isoformat()
            candidatas = [(d, taxa) for (a, d), taxa in hist.items() if a == int(ano) and d <= alvo]
            if candidatas:
                d, taxa = max(candidatas)
                extra.append(f"{dias}d {x['taxa_compra_pct'] - taxa:+.3f} pp")
            else:
                extra.append(f"{dias}d n/d")
        partes.append(f"{ano}: compra {x['taxa_compra_pct']:.3f}% (" + ", ".join(extra) + ")")
    return "\n".join(partes)


def principal(args=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="busca e calcula sem gravar nem notificar")
    parser.add_argument("--teste-notificacao", action="store_true", help="envia notificação de teste")
    parser.add_argument("--resumo", action="store_true", help="força resumo diário")
    parser.add_argument("--config", type=Path, default=PADRAO_CONFIG, help="caminho do arquivo TOML")
    parser.add_argument("--testes", action="store_true", help="executa testes simples locais")
    op = parser.parse_args(args)
    if op.testes:
        assert parse_csv("Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\nTesouro IPCA+;15/05/2035;28/10/2026;8,10;8,20;1000,00;990,00\nTesouro IPCA+ com Juros Semestrais;15/05/2035;28/10/2026;7,0;7,1;100;99\n".encode())[0]["taxa_compra_pct"] == 8.1
        assert cruzamentos(7.9, 8.1, [8.0]) == [(8.0, "alta")]
        assert cruzamentos(8.1, 7.9, [8.0]) == [(8.0, "queda")]
        print("Testes básicos: OK")
        return 0
    cfg = carregar_config(op.config)
    pasta = Path(cfg.get("armazenamento", {}).get("diretorio", PADRAO_DIR)).expanduser()
    log = configurar_log(pasta, somente_console=op.dry_run)
    if op.teste_notificacao:
        notificar("Teste do Monitor Tesouro", "Notificação de teste configurada.", cfg.get("notificacoes", {}), log)
        return 0
    try:
        fonte = cfg.get("fonte", {})
        registros = parse_csv(baixar(fonte.get("url", PADRAO_URL), int(fonte.get("timeout_segundos", 45))))
        hoje = date.today()
        estado_path, hist_path = pasta / "estado.json", pasta / "historico.csv"
        estado = ler_json(estado_path, {"taxas": {}, "notificados": {}, "resumo_enviado_em": None})
        limites = sorted(float(x) for x in cfg.get("alertas", {}).get("patamares_pct", [7.0, 8.0, 9.0, 10.0]))
        eventos = []
        for x in registros:
            chave = x["vencimento"].isoformat()
            anterior = estado.get("taxas", {}).get(chave)
            if anterior is not None:
                for p, direcao in cruzamentos(float(anterior), x["taxa_compra_pct"], limites):
                    eventos.append((x, p, direcao))
        texto = "\n".join(f"{x['titulo']} ({x['vencimento'].year}): taxa de compra cruzou {p:.2f}% em {direcao} ({x['taxa_compra_pct']:.3f}%)." for x, p, direcao in eventos)
        if not op.dry_run:
            if eventos:
                notificar("Cruzamento de taxa IPCA+", texto, cfg.get("notificacoes", {}), log)
                for x, p, direcao in eventos:
                    estado.setdefault("notificados", {}).setdefault(x["vencimento"].isoformat(), {})[f"{p:.3f}:{direcao}"] = hoje.isoformat()
            gravar_historico(hist_path, registros, hoje)
            estado["taxas"] = {x["vencimento"].isoformat(): x["taxa_compra_pct"] for x in registros}
            if op.resumo or (cfg.get("resumo", {}).get("habilitado", False) and estado.get("resumo_enviado_em") != hoje.isoformat()):
                notificar("Resumo diário Tesouro IPCA+", resumo(registros, hist_path, cfg), cfg.get("notificacoes", {}), log)
                estado["resumo_enviado_em"] = hoje.isoformat()
            salvar_json(estado_path, estado)
        print(f"Data-base {registros[0]['data_base']:%d/%m/%Y}: {len(registros)} vencimentos IPCA+ principal.")
        if eventos:
            print(texto)
        else:
            print("Nenhum cruzamento novo.")
        return 0
    except (URLError, TimeoutError, OSError, ValueError, KeyError, csv.Error) as e:
        log.exception("Execução interrompida: %s", e)
        print(f"Erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
