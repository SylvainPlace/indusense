import unittest

from bronze_incidents import TYPES_INCIDENTS, encoder_copy, transformer_incident


class TestBronzeIncidents(unittest.TestCase):
    def test_preserve_les_valeurs_et_pseudonymise_les_deux_champs(self):
        ligne = [""] * len(TYPES_INCIDENTS)
        colonnes = list(TYPES_INCIDENTS)
        ligne[colonnes.index("operator_name")] = "exemple"
        ligne[colonnes.index("operator_badge")] = "exemple"
        ligne[colonnes.index("machine_id")] = "001"
        sortie = transformer_incident(ligne, b"sel-test", b"cle-test")
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
        sortie = transformer_incident(ligne, b"sel-test", b"cle-test")
        self.assertEqual(sortie, transformer_incident(ligne, b"sel-test", b"cle-test"))
        self.assertNotEqual(sortie[-1], transformer_incident(autre, b"sel-test", b"cle-test")[-1])

    def test_copy_preserve_les_caracteres_speciaux_et_les_champs_vides(self):
        self.assertEqual(encoder_copy(""), "")
        self.assertEqual(encoder_copy("\\.\tligne\nsuivante\r"), r"\\.\tligne\nsuivante\r")


if __name__ == "__main__":
    unittest.main()
