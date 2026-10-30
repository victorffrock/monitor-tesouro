import tempfile
import unittest
from datetime import date
from pathlib import Path

from monitor_tesouro.core import carregar_historico


class HistoryTests(unittest.TestCase):
    def test_groups_and_sorts_points_by_maturity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "historico.csv"
            path.write_text(
                "data_execucao,data_base,vencimento,titulo,taxa_compra_pct,taxa_venda_pct,pu_compra,pu_venda\n"
                "2026-10-30,2026-10-30,2035-05-15,Tesouro IPCA+,8.2,8.3,1000,990\n"
                "2026-10-29,2026-10-29,2035-05-15,Tesouro IPCA+,8.1,8.2,1001,991\n"
                "2026-10-30,data-invalida,2045-05-15,Tesouro IPCA+,8.4,8.5,900,890\n",
                encoding="utf-8",
            )

            series = carregar_historico(path)

        self.assertEqual(list(series), [2035])
        self.assertEqual(
            [point["data_base"] for point in series[2035]],
            [date(2026, 10, 29), date(2026, 10, 30)],
        )
        self.assertEqual(series[2035][-1]["taxa_venda_pct"], 8.3)

    def test_missing_history_returns_empty_series(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            series = carregar_historico(Path(temp_dir) / "missing.csv")
        self.assertEqual(series, {})


if __name__ == "__main__":
    unittest.main()
