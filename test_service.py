import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import service


class StateIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.game = self.root / "Game"; self.game.mkdir()
        (self.game / "Mahjong-JP.exe").touch()
        self.local = self.root / "local"; self.roaming = self.root / "roaming"

    def tearDown(self):
        self.temp.cleanup()

    def test_existing_matching_backup_is_reused(self):
        folder = self.roaming / "akagiplus/riichicity-local"; folder.mkdir(parents=True)
        (folder / "install.json").write_text(json.dumps({"target": str(service.installer.target_for(self.game))}))
        self.assertEqual(service.choose_state(self.game, local=self.local, roaming=self.roaming), folder)

    def test_different_installations_use_separate_folders(self):
        first = service.choose_state(self.game, local=self.local, roaming=self.roaming)
        other = self.root / "other"; other.mkdir(); (other / "Mahjong-JP.exe").touch()
        second = service.choose_state(other, local=self.local, roaming=self.roaming)
        self.assertNotEqual(first, second)
        self.assertFalse(first.exists())

    def test_corrupt_journal_is_not_overwritten(self):
        folder = self.roaming / "akagiplus/riichicity-local"; folder.mkdir(parents=True)
        journal = folder / "install.json"; journal.write_text("invalid")
        with self.assertRaises(ValueError):
            service.choose_state(self.game, local=self.local, roaming=self.roaming)
        self.assertEqual(journal.read_text(), "invalid")

    def test_failed_install_does_not_save_a_successful_selection(self):
        with patch.object(service, "choose_state", return_value=self.local), patch.object(service, "apply_patch", side_effect=ValueError("failure")), patch.object(service.installer, "atomic") as write:
            with self.assertRaises(ValueError):service.perform("install", str(self.game))
            write.assert_not_called()

    def test_previous_name_preferences_are_read(self):
        old = self.root / "previous"; old.mkdir()
        (old / "gui.json").write_text(json.dumps({"game": str(self.game)}))
        with patch.object(service, "data_root", return_value=self.local), patch.object(service, "legacy_data_root", return_value=old):
            self.assertEqual(service.load_game(), str(self.game))

    def test_previous_name_recovery_record_is_reused(self):
        old = self.root / "previous"
        folder = service.choose_state(self.game, local=old, roaming=self.roaming, legacy=self.root / "none")
        folder.mkdir(parents=True)
        (folder / "install.json").write_text(json.dumps({"target": str(service.installer.target_for(self.game))}))
        self.assertEqual(service.choose_state(self.game, local=self.local, roaming=self.roaming, legacy=old), folder)

    def test_executable_path_is_accepted(self):
        self.assertEqual(service.normalize_game(str(self.game / "Mahjong-JP.exe")), self.game.resolve())


if __name__ == "__main__":
    unittest.main()
