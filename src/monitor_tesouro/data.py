#!/usr/bin/env python3
# Copyright (C) 2026 Victor Ferreira Franco
# SPDX-License-Identifier: GPL-3.0-only
"""Carregamento, cache e combinação do histórico público e local.

O CSV do Tesouro Transparente é a fonte principal. Um cache comprimido permite
reabrir o gráfico sem rede e os validadores protegem o arquivo local de respostas
incompletas ou de mudanças inesperadas no formato remoto.
"""

from __future__ import annotations

import csv
from datetime import date
import gzip
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import core

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "monitor-tesouro"
CACHE_PATH = CACHE_DIR / "historico.json.gz"
LEGACY_HISTORY = core.PADRAO_DIR / "historico.csv"
CACHE_VERSION = 1


def _key(row: dict) -> tuple[date, date]:
    """Identifica um ponto pela data de referência e pelo vencimento do título."""
    return row["data_base"], row["vencimento"]


def merge_history(*collections: list[dict]) -> list[dict]:
    """Combina pontos, preferindo coleções mais recentes quando há duplicatas."""
    merged = {}
    for collection in collections:
        for row in collection:
            merged[_key(row)] = row
    return sorted(merged.values(), key=lambda row: (_key(row)))


def load_legacy_history(path: Path) -> list[dict]:
    """Importa as observações que versões anteriores guardaram em CSV local."""
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", newline="") as stream:
        for source in csv.DictReader(stream):
            try:
                rows.append({
                    "data_base": date.fromisoformat(source["data_base"]),
                    "vencimento": date.fromisoformat(source["vencimento"]),
                    "titulo": source.get("titulo") or "Tesouro IPCA+",
                    "taxa_compra_pct": float(source["taxa_compra_pct"]),
                    "taxa_venda_pct": float(source["taxa_venda_pct"]),
                    "pu_compra": float(source.get("pu_compra") or 0),
                    "pu_venda": float(source.get("pu_venda") or 0),
                })
            except (KeyError, TypeError, ValueError):
                continue
    return merge_history(rows)


def read_cache(path: Path = CACHE_PATH) -> tuple[list[dict], dict]:
    """Lê e valida o cache gzipado; arquivo ausente ou corrompido vira cache vazio."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            saved = json.load(stream)
        if saved.get("version") != CACHE_VERSION or not isinstance(saved.get("rows"), list):
            return [], {}
        rows = []
        for item in saved["rows"]:
            rows.append({
                **item,
                "data_base": date.fromisoformat(item["data_base"]),
                "vencimento": date.fromisoformat(item["vencimento"]),
            })
        return merge_history(rows), {
            "etag": saved.get("etag", ""),
            "last_modified": saved.get("last_modified", ""),
        }
    except (OSError, EOFError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [], {}


def write_cache(rows: list[dict], metadata: dict, path: Path = CACHE_PATH) -> None:
    """Grava o cache de forma atômica para uma interrupção não corrompê-lo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "etag": metadata.get("etag", ""),
        "last_modified": metadata.get("last_modified", ""),
        "rows": [
            {
                **row,
                "data_base": row["data_base"].isoformat(),
                "vencimento": row["vencimento"].isoformat(),
            }
            for row in merge_history(rows)
        ],
    }
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
            temp_path = Path(stream.name)
            with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed:
                compressed.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _fetch(url: str, timeout: int, metadata: dict, opener=urlopen) -> tuple[bytes | None, dict]:
    """Busca o CSV com validadores HTTP para evitar baixar o arquivo sem mudanças."""
    headers = {"User-Agent": "monitor-tesouro/1.0", "Accept": "text/csv"}
    if metadata.get("etag"):
        headers["If-None-Match"] = metadata["etag"]
    if metadata.get("last_modified"):
        headers["If-Modified-Since"] = metadata["last_modified"]
    request = Request(url, headers=headers)
    try:
        with opener(request, timeout=timeout) as response:
            content = response.read()
            if not content or b"<html" in content[:500].lower():
                raise ValueError("A fonte oficial não retornou um CSV válido.")
            return content, {
                "etag": response.headers.get("ETag", ""),
                "last_modified": response.headers.get("Last-Modified", ""),
            }
    except HTTPError as error:
        if error.code == 304:
            return None, metadata
        raise


def get_history(
    url: str = core.PADRAO_URL,
    timeout: int = 60,
    cache_path: Path = CACHE_PATH,
    legacy_path: Path = LEGACY_HISTORY,
    opener=urlopen,
) -> tuple[list[dict], str]:
    """Atualiza o histórico, ou devolve a última cópia válida em caso de falha de rede."""
    cached, metadata = read_cache(cache_path)
    legacy = load_legacy_history(legacy_path)
    try:
        content, new_metadata = _fetch(url, timeout, metadata, opener)
        if content is None:
            rows = merge_history(legacy, cached)
            status = "Histórico oficial verificado; sem mudanças desde a última atualização."
        else:
            # Uma resposta CSV válida pode não conter toda a série; exigir uma
            # série útil impede substituir por engano um cache mais completo.
            downloaded = core.parse_csv(content, somente_recente=False)
            # O cache preserva datas antigas que a fonte possa retirar; a resposta
            # atual ganha em caso de duplicata para corrigir qualquer valor antigo.
            rows = merge_history(legacy, cached, downloaded)
            status = "Histórico atualizado pelo Tesouro Transparente."
        write_cache(rows, new_metadata, cache_path)
        return rows, status
    except Exception as error:
        fallback = merge_history(legacy, cached)
        if fallback:
            return fallback, f"Sem conexão com a fonte oficial; exibindo o histórico salvo. ({error})"
        raise


def format_rate(value: float) -> str:
    """Formata percentual conforme convenção brasileira."""
    return f"{value:.3f}%".replace(".", ",")


def format_currency(value: float) -> str:
    """Formata preço em reais conforme convenção brasileira."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
