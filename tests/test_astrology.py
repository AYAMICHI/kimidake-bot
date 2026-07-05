from datetime import date
from unittest import TestCase

from src.kimidake_bot.logic.astrology import (
    life_path_reading_tendency,
    zodiac_reading_tendency,
    zodiac_sign,
)
from src.kimidake_bot.logic.numerology import life_path_number


class AstrologyTest(TestCase):
    def test_zodiac_sign(self):
        self.assertEqual(zodiac_sign(date(2000, 11, 22)), "蠍座")
        self.assertEqual(zodiac_sign(date(2000, 11, 23)), "射手座")
        self.assertEqual(zodiac_sign(date(2000, 1, 19)), "山羊座")
        self.assertEqual(zodiac_sign(date(2000, 1, 20)), "水瓶座")

    def test_life_path_reuses_existing_numerology(self):
        self.assertEqual(life_path_number("2000-11-22"), 8)

    def test_birth_reading_tendencies_provide_interpretation_cues(self):
        self.assertIn("可能性", zodiac_reading_tendency("蠍座"))
        self.assertIn("現実の成果や形", life_path_reading_tendency(8))
