import tempfile
import unittest
from pathlib import Path

from bronze import encoder_copy, lire_tables_machine, transformer_ligne


class TestBronzeSql(unittest.TestCase):
    def test_insert_reordonne_et_valeurs_absentes(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "machine.sql.txt"
            source.write_text(
                """
                CREATE TABLE machine (machine_code TEXT PRIMARY KEY, note TEXT, active BOOLEAN DEFAULT TRUE);
                INSERT INTO machine (note, machine_code) VALUES ('', 'M001'), (NULL, 'M002');
                CREATE TABLE maintenance (id INTEGER PRIMARY KEY, machine_code TEXT REFERENCES machine(machine_code));
                INSERT INTO maintenance VALUES (1, 'M001');
                """,
                encoding="utf-8",
            )
            machine, maintenance = list(lire_tables_machine(source))

        self.assertEqual(machine[1], {"machine_code": "IDENTITY", "note": "TEXT", "active": "BOOLEAN"})
        self.assertEqual(machine[2], [["M001", "", None], ["M002", None, None]])
        self.assertEqual(maintenance[1], {"id": "IDENTITY", "machine_code": "IDENTITY"})
        self.assertEqual(maintenance[2], [["1", "M001"]])

    def test_null_et_chaine_vide_ont_des_empreintes_distinctes(self):
        types = {"note": "TEXT"}
        self.assertNotEqual(
            transformer_ligne([None], types, b"cle-test")[-1],
            transformer_ligne([""], types, b"cle-test")[-1],
        )
        self.assertEqual(encoder_copy(None), r"\N")
        self.assertEqual(encoder_copy(r"\N"), r"\\N")
