import unittest

from bronze import TYPES_INCIDENTS, TYPES_TELEMETRIE, encoder_copy, transformer_ligne


class TestBronzeIncidents(unittest.TestCase):
    def test_preserve_les_valeurs_et_pseudonymise_les_deux_champs(self):
        ligne = [""] * len(TYPES_INCIDENTS)
        colonnes = list(TYPES_INCIDENTS)
        ligne[colonnes.index("operator_name")] = "exemple"
        ligne[colonnes.index("operator_badge")] = "exemple"
        ligne[colonnes.index("machine_id")] = "001"
        sortie = transformer_ligne(ligne, TYPES_INCIDENTS, b"cle-test", sel_operateur=b"sel-test")
        champs = dict(zip(colonnes, sortie[:-1:2], strict=True))

        self.assertEqual(sortie[1:-1:2], list(TYPES_INCIDENTS.values()))
        self.assertEqual(champs["machine_id"], "001")
        self.assertEqual(champs["comment"], "")
        self.assertRegex(champs["operator_name"], r"^[0-9a-f]{64}$")
        self.assertRegex(champs["operator_badge"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(champs["operator_name"], champs["operator_badge"])

    def test_empreinte_stable_et_sensible_aux_frontieres_des_champs(self):
        ligne = ["a", "b,c"] + [""] * (len(TYPES_INCIDENTS) - 2)
        autre = ["a,b", "c"] + ligne[2:]
        sortie = transformer_ligne(ligne, TYPES_INCIDENTS, b"cle-test", sel_operateur=b"sel-test")
        self.assertEqual(sortie, transformer_ligne(ligne, TYPES_INCIDENTS, b"cle-test", sel_operateur=b"sel-test"))
        self.assertNotEqual(sortie[-1], transformer_ligne(autre, TYPES_INCIDENTS, b"cle-test", sel_operateur=b"sel-test")[-1])

    def test_telemetrie_preserve_les_mesures_et_les_champs_vides(self):
        ligne = ["MACH-01", "2026-01-01 10:00:00", "01.50", "", "1e2", "1200", "0"]
        sortie = transformer_ligne(ligne, TYPES_TELEMETRIE, b"cle-test")

        self.assertEqual(sortie[:-1:2], ligne)
        self.assertEqual(sortie[1:-1:2], ["IDENTITY", "DATETIME", *["NUMERIC"] * 5])
        self.assertRegex(sortie[-1], r"^[0-9a-f]{64}$")

    def test_copy_preserve_les_caracteres_speciaux_et_les_champs_vides(self):
        self.assertEqual(encoder_copy(""), "")
        self.assertEqual(encoder_copy("\\.\tligne\nsuivante\r"), r"\\.\tligne\nsuivante\r")


if __name__ == "__main__":
    unittest.main()
