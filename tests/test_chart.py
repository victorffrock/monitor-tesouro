import unittest
from datetime import date

from monitor_tesouro.chart import maturity_dates, point_coordinates, points_for_period, rate_bounds


def point(day, maturity, buy, sell):
    return {
        "data_base": date.fromisoformat(day),
        "vencimento": date.fromisoformat(maturity),
        "taxa_compra_pct": buy,
        "taxa_venda_pct": sell,
    }


class ChartSeriesTests(unittest.TestCase):
    def setUp(self):
        self.maturity = date(2035, 5, 15)
        self.rows = [
            point("2024-01-10", "2035-05-15", 5.0, 5.2),
            point("2024-04-10", "2035-05-15", 6.0, 6.2),
            point("2024-04-10", "2040-05-15", 6.5, 6.7),
        ]

    def test_lists_unique_maturities_in_order(self):
        self.assertEqual(maturity_dates(self.rows), [self.maturity, date(2040, 5, 15)])

    def test_selects_exact_maturity_and_sorts_points(self):
        rows = list(reversed(self.rows))
        result = points_for_period(rows, self.maturity, 0)
        self.assertEqual([row["data_base"] for row in result], [date(2024, 1, 10), date(2024, 4, 10)])

    def test_period_cutoff_is_relative_to_given_day(self):
        result = points_for_period(
            self.rows, self.maturity, 60, today=date(2024, 4, 10)
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["data_base"], date(2024, 4, 10))

    def test_rate_bounds_keep_flat_series_visible(self):
        low, high = rate_bounds([point("2024-01-10", "2035-05-15", 7, 7)])
        self.assertLess(low, 7)
        self.assertGreater(high, 7)

    def test_coordinates_map_first_and_last_date_to_chart_edges(self):
        start = point("2024-01-10", "2035-05-15", 5, 5.2)
        end = point("2024-04-10", "2035-05-15", 6, 6.2)
        x1, _ = point_coordinates(start, start["data_base"], end["data_base"], 4, 7,
                                  (10, 20, 210, 120), "taxa_compra_pct")
        x2, _ = point_coordinates(end, start["data_base"], end["data_base"], 4, 7,
                                  (10, 20, 210, 120), "taxa_compra_pct")
        self.assertEqual((x1, x2), (10, 210))


if __name__ == "__main__":
    unittest.main()
