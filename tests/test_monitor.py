import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from monitor_tesouro.core import (
    cruzamentos,
    data_br,
    gravar_historico,
    ler_json,
    numero,
    parse_csv,
    salvar_json,
)


class ParserTests(unittest.TestCase):
    def test_csv_brasileiro_filtra_ipca_principal(self):
        csv_text = (
            "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\n"
            "Tesouro IPCA+;15/05/2035;28/10/2026;8,10;8,20;1.000,00;990,00\n"
            "Tesouro IPCA+ com Juros Semestrais;15/05/2035;28/10/2026;7,0;7,1;100,00;99,00\n"
        ).encode("utf-8")
        rows = parse_csv(csv_text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["taxa_compra_pct"], 8.1)
        self.assertEqual(rows[0]["pu_compra"], 1000.0)

    def test_seleciona_apenas_a_data_base_mais_recente(self):
        csv_text = (
            "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\n"
            "Tesouro IPCA+;15/05/2035;27/10/2026;7,10;7,20;900,00;890,00\n"
            "Tesouro IPCA+;15/05/2035;28/10/2026;8,10;8,20;1.000,00;990,00\n"
        ).encode("utf-8")
        rows = parse_csv(csv_text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data_base"], date(2026, 10, 28))
        self.assertEqual(rows[0]["taxa_compra_pct"], 8.1)

    def test_mantem_serie_historica_completa_quando_solicitada(self):
        csv_text = (
            "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\n"
            "Tesouro IPCA+;15/05/2035;27/10/2026;7,10;7,20;900,00;890,00\n"
            "Tesouro IPCA+;15/05/2035;28/10/2026;8,10;8,20;1.000,00;990,00\n"
            "Tesouro IPCA+;15/05/2040;27/10/2026;7,30;7,40;800,00;790,00\n"
        ).encode("utf-8")
        rows = parse_csv(csv_text, somente_recente=False)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["data_base"] for r in rows], [
            date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 27)
        ])

    def test_rejeita_csv_sem_colunas_esperadas(self):
        with self.assertRaisesRegex(ValueError, "Cabeçalhos esperados"):
            parse_csv(b"coluna;outra\nx;y\n")

    def test_numero_reconhece_formato_brasileiro_e_valor_invalido(self):
        self.assertEqual(numero("1.234,56"), 1234.56)
        self.assertEqual(numero("8,10%"), 8.1)
        self.assertIsNone(numero(""))
        self.assertIsNone(numero("inválido"))

    def test_data_br_valida_e_rejeita_data_incorreta(self):
        self.assertEqual(data_br("28/10/2026"), date(2026, 10, 28))
        with self.assertRaises(ValueError):
            data_br("2026-10-28")


class ThresholdTests(unittest.TestCase):
    def test_detecta_cruzamento_de_alta_e_queda(self):
        self.assertEqual(cruzamentos(7.9, 8.1, [8.0]), [(8.0, "alta")])
        self.assertEqual(cruzamentos(8.1, 7.9, [8.0]), [(8.0, "queda")])

    def test_nao_repete_sem_nova_travessia(self):
        self.assertEqual(cruzamentos(8.1, 8.2, [8.0]), [])

    def test_cruzamento_inclui_patamar_no_limite(self):
        self.assertEqual(cruzamentos(7.9, 8.0, [8.0]), [(8.0, "alta")])
        self.assertEqual(cruzamentos(8.1, 8.0, [8.0]), [(8.0, "queda")])


class PersistenceTests(unittest.TestCase):
    def test_salva_e_carrega_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            dado = {"taxa": 8.1, "vencimento": "2035-05-15"}
            salvar_json(path, dado)
            self.assertEqual(ler_json(path, {}), dado)

    def test_historico_nao_duplica_data_base_e_vencimento(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "historico.csv"
            linhas = [{
                "data_base": date(2026, 10, 28),
                "vencimento": date(2035, 5, 15),
                "titulo": "Tesouro IPCA+",
                "taxa_compra_pct": 8.1,
                "taxa_venda_pct": 8.2,
                "pu_compra": 1000.0,
                "pu_venda": 990.0,
            }]
            gravar_historico(path, linhas, date(2026, 10, 29))
            gravar_historico(path, linhas, date(2026, 10, 30))
            with path.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data_base"], "2026-10-28")
