import csv
import hmac
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bronze import TYPES_TELEMETRIE, encoder_champs, sha256_source
from silver import choisir_telemetrie, convertir, decrire_absences


class TestSilver(unittest.TestCase):
    def test_choisit_la_premiere_occurrence_csv_meme_si_bronze_est_desordonne(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "telemetry.csv"
            base = ["MACH-01", "2025-06-01 06:00:00", "", "2.1", "3", "4", "5"]
            reemise = [*base]
            reemise[2] = "30"
            with source.open("w", encoding="utf-8", newline="") as fichier:
                writer = csv.writer(fichier)
                writer.writerow(TYPES_TELEMETRIE)
                writer.writerows((base, reemise))

            def ligne_bronze(valeurs):
                return {
                    **dict(zip(TYPES_TELEMETRIE, valeurs, strict=True)),
                    "bronze_run_id": "lot-test",
                    "bronze_hash": hmac.digest(b"cle-test", encoder_champs(valeurs), "sha256").hex(),
                }

            initiale, suivante = map(ligne_bronze, (base, reemise))
            choisies, journal = choisir_telemetrie(
                [suivante, initiale], source, sha256_source(source), b"cle-test",
            )
            self.assertEqual(choisies, [(1, initiale)])
            self.assertEqual(journal[0]["ligne_ecartee"], 2)
            self.assertEqual(journal[0]["hash_ecarte"], suivante["bronze_hash"])
            self.assertIsNone(convertir(choisies[0][1]["temperature_c"], "NUMERIC", "telemetry.temperature_c"))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                choisir_telemetrie([initiale, suivante], source, "autre-version", b"cle-test")

    def test_distingue_champ_manquant_et_heure_absente(self):
        h = datetime(2025, 6, 1, 6, tzinfo=UTC)
        lignes = [
            dict(bronze_run_id="lot", machine_id="M1", timestamp=h + timedelta(hours=i),
                 signaux=[], mesures_manquantes=["pressure_bar"] if i < 2 else [])
            for i in (0, 1, 3)
        ]
        periodes, absentes = decrire_absences(lignes)
        self.assertEqual(len(periodes), 1)
        self.assertEqual(periodes[0]["debut_utc"], h - timedelta(hours=1))
        self.assertEqual(periodes[0]["fin_utc"], h + timedelta(hours=1))
        self.assertEqual(periodes[0]["nombre_releves"], 2)
        self.assertEqual(absentes[0]["timestamp_attendu_utc"], h + timedelta(hours=2))
        self.assertEqual(absentes[0]["etat_machine"], "INCONNU")
