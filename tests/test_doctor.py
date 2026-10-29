"""doctor.py parses both ComfyUI object_info input formats; no network or GPU."""

import importlib.util
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location(
    "doctor", Path(__file__).resolve().parent.parent / "scripts" / "doctor.py")
doctor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doctor)


class LoaderOptionsTests(unittest.TestCase):
    def test_legacy_list_format(self):
        self.assertEqual(doctor.loader_options([["a.safetensors", "b.safetensors"], {}]),
                         ["a.safetensors", "b.safetensors"])

    def test_combo_options_format(self):
        self.assertEqual(doctor.loader_options(["COMBO", {"options": ["a.safetensors"]}]),
                         ["a.safetensors"])

    def test_unknown_or_empty_format(self):
        self.assertEqual(doctor.loader_options([]), [])
        self.assertEqual(doctor.loader_options(["STRING", {}]), [])
        self.assertEqual(doctor.loader_options(["COMBO", {}]), [])


if __name__ == "__main__":
    unittest.main()
