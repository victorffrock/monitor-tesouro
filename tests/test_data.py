import tempfile
import unittest
from datetime import date
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError

from monitor_tesouro.data import get_history, merge_history, read_cache, write_cache


def row(day, buy):
    return {
        "data_base": date.fromisoformat(day),
        "vencimento": date(2035, 5, 15),
        "titulo": "Tesouro IPCA+",
        "taxa_compra_pct": buy,
        "taxa_venda_pct": buy + 0.1,
        "pu_compra": 1000.0,
        "pu_venda": 990.0,
    }


class Response:
    def __init__(self, content, headers=None):
        self.content = content
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.content


class HistoryCacheTests(unittest.TestCase):
    def test_cache_round_trip_preserves_dates_and_validators(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json.gz"
            write_cache([row("2024-01-10", 5.2)], {"etag": '"daily-1"'}, path)
            rows, metadata = read_cache(path)
        self.assertEqual(rows[0]["data_base"], date(2024, 1, 10))
        self.assertEqual(metadata["etag"], '"daily-1"')

    def test_merge_deduplicates_and_later_collection_wins(self):
        older = row("2024-01-10", 5.2)
        updated = row("2024-01-10", 5.4)
        result = merge_history([older], [row("2023-12-10", 5.0), updated])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["taxa_compra_pct"], 5.4)

    def test_offline_mode_returns_valid_cached_history(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "history.json.gz"
            write_cache([row("2024-01-10", 5.2)], {}, cache)

            def offline(*_args, **_kwargs):
                raise URLError("sem rede")

            rows, message = get_history(
                cache_path=cache,
                legacy_path=Path(directory) / "old.csv",
                opener=offline,
            )
        self.assertEqual(len(rows), 1)
        self.assertIn("histórico salvo", message)

    def test_not_modified_request_reuses_cache_and_sends_etag(self):
        csv_data = (
            "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\n"
            "Tesouro IPCA+;15/05/2035;10/01/2024;5,20;5,30;1.000,00;990,00\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "history.json.gz"

            def first_request(_request, timeout):
                self.assertEqual(timeout, 5)
                return Response(csv_data, {"ETag": '"source-1"'})

            initial, _ = get_history(
                url="https://example.test/history.csv",
                timeout=5,
                cache_path=cache,
                legacy_path=Path(directory) / "old.csv",
                opener=first_request,
            )
            headers = Message()
            not_modified = HTTPError(
                "https://example.test/history.csv", 304, "Not Modified", headers, None
            )

            def unchanged_request(request, timeout):
                self.assertEqual(request.get_header("If-none-match"), '"source-1"')
                raise not_modified

            cached, message = get_history(
                url="https://example.test/history.csv",
                timeout=5,
                cache_path=cache,
                legacy_path=Path(directory) / "old.csv",
                opener=unchanged_request,
            )
        self.assertEqual(initial, cached)
        self.assertIn("sem mudanças", message)


if __name__ == "__main__":
    unittest.main()
