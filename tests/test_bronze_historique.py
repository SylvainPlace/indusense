import csv
import io
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from bronze import TYPES_TELEMETRIE, preparer_chargement, sha256_source


class TestHistoriqueBronze(unittest.TestCase):
    def test_rejeu_garde_les_doublons_et_enregistre_un_nouveau_lot(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "telemetry.csv"
            ligne = ["MACH-01", "2026-01-01 00:00:00", "1", "2", "3", "4", "5"]
            with source.open("w", encoding="utf-8", newline="") as fichier:
                writer = csv.writer(fichier)
                writer.writerow(TYPES_TELEMETRIE)
                writer.writerows([ligne, ligne])

            lots = []
            for _ in range(2):
                flux = io.BytesIO()
                self.assertEqual(
                    preparer_chargement(flux, source, "telemetry", b"cle-test"),
                    {"telemetry": 2},
                )
                script = flux.getvalue().decode()
                lignes_bronze = script.split("FROM STDIN;\n", 1)[1].split("\\.\n", 1)[0].splitlines()
                self.assertEqual(len(lignes_bronze), 2)
                self.assertEqual(lignes_bronze[0], lignes_bronze[1])
                historique = script.rsplit("FROM STDIN;\n", 1)[1].splitlines()[0].split("\t")
                lots.append(UUID(historique[0]))
                self.assertEqual(historique[1:4], ["telemetry", source.name, sha256_source(source)])
                self.assertEqual(historique[-1], "2")
                self.assertTrue(script.endswith("\\.\nCOMMIT;\n"))

            self.assertNotEqual(*lots)
