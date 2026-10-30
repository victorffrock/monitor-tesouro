import unittest

from monitor_tesouro.core import cruzamentos, parse_csv


class ParserTests(unittest.TestCase):
    def test_csv_brasileiro_filtra_ipca_principal(self):
        csv = (
            "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manhã;Taxa Venda Manhã;PU Compra Manhã;PU Venda Manhã\n"
            "Tesouro IPCA+;15/05/2035;28/10/2026;8,10;8,20;1.000,00;990,00\n"
            "Tesouro IPCA+ com Juros Semestrais;15/05/2035;28/10/2026;7,0;7,1;100,00;99,00\n"
        ).encode("utf-8")
        rows = parse_csv(csv)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["taxa_compra_pct"], 8.1)
        self.assertEqual(rows[0]["pu_compra"], 1000.0)

    def test_rejeita_csv_sem_colunas_esperadas(self):
        with self.assertRaisesRegex(ValueError, "Cabeçalhos esperados"):
            parse_csv(b"coluna;outra\nx;y\n")


class ThresholdTests(unittest.TestCase):
    def test_detecta_cruzamento_de_alta_e_queda(self):
        self.assertEqual(cruzamentos(7.9, 8.1, [8.0]), [(8.0, "alta")])
        self.assertEqual(cruzamentos(8.1, 7.9, [8.0]), [(8.0, "queda")])

    def test_nao_repete_sem_nova_travessia(self):
        self.assertEqual(cruzamentos(8.1, 8.2, [8.0]), [])


if __name__ == "__main__":
    unittest.main()
