import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
  "psws_util", Path(__file__).resolve().parents[1] / "psws" / "util.py"
)
util = importlib.util.module_from_spec(spec)
spec.loader.exec_module(util)


class StationDirectoryTests(unittest.TestCase):
  def setUp(self):
    directory = tempfile.TemporaryDirectory()
    self.addCleanup(directory.cleanup)
    self.root = Path(directory.name)
    self.default = self.root / "home"
    self.fallback = self.root / "data"
    self.fallback.mkdir()
    for replacement in (
      patch.object(util, "STATION_DIR", str(self.default)),
      patch.object(util, "__file__", str(self.root / "psws" / "util.py")),
      patch.dict(os.environ, {}, clear=True),
    ):
      replacement.start()
      self.addCleanup(replacement.stop)
    util.cli.cache_clear()
    self.addCleanup(util.cli.cache_clear)

  def parse(self, *arguments, endpoint=None):
    output = io.StringIO()
    with patch.object(sys, "argv", ["test", *arguments]):
      with contextlib.redirect_stderr(output):
        options = util.cli(endpoint=endpoint)
    return options, output.getvalue()

  def test_available_default_does_not_fall_back(self):
    (self.default / "N000008").mkdir(parents=True)
    options, message = self.parse()
    self.assertEqual(options["station_dir"], self.default)
    self.assertEqual(message, "")

  def test_empty_default_uses_fallback_and_logs(self):
    self.default.mkdir()
    for endpoint in (None, "data"):
      with self.subTest(endpoint=endpoint):
        options, message = self.parse("--debug", endpoint=endpoint)
        self.assertEqual(options["station_dir"], self.fallback.resolve())
        self.assertIn("no matching station subdirectories", message)

  def test_default_requires_matching_directories_not_files(self):
    self.default.mkdir()
    (self.default / "other").mkdir()
    (self.default / "N000008").write_text("not a directory")
    options, message = self.parse("--debug")
    self.assertEqual(options["station_dir"], self.fallback.resolve())
    self.assertIn("no matching station subdirectories", message)

  def test_fallback_is_silent_without_debug(self):
    for exists in (False, True):
      with self.subTest(default_exists=exists):
        if exists:
          self.default.mkdir()
        util.cli.cache_clear()
        options, message = self.parse()
        self.assertEqual(options["station_dir"], self.fallback.resolve())
        self.assertEqual(message, "")

  def test_default_uses_selected_station_regex(self):
    (self.default / "custom").mkdir(parents=True)
    options, message = self.parse("--station-dir-regex", "custom")
    self.assertEqual(options["station_dir"], self.default)
    self.assertEqual(message, "")

  def test_explicit_empty_default_does_not_fall_back(self):
    self.default.mkdir()
    options, message = self.parse("--station-dir", str(self.default))
    self.assertEqual(options["station_dir"], self.default)
    self.assertEqual(message, "")

  def test_missing_default_uses_script_relative_fallback_and_logs(self):
    for endpoint in (None, "data"):
      with self.subTest(endpoint=endpoint):
        options, message = self.parse("--debug", endpoint=endpoint)
        self.assertEqual(options["station_dir"], self.fallback.resolve())
        self.assertIn(str(self.default), message)
        self.assertIn(str(self.fallback.resolve()), message)

  def test_default_file_uses_fallback(self):
    self.default.write_text("not a directory")
    options, message = self.parse("--debug")
    self.assertEqual(options["station_dir"], self.fallback.resolve())
    self.assertIn("fallback", message)

  def test_explicit_missing_default_does_not_fall_back(self):
    options, message = self.parse("--station-dir", str(self.default))
    self.assertEqual(options["station_dir"], self.default)
    self.assertEqual(message, "")
    with self.assertRaisesRegex(util.Error, "does not exist"):
      util.validate_station_dir(options["station_dir"])

  def test_environment_path_overrides_cli_without_fallback(self):
    missing = self.root / "missing"
    with patch.dict(os.environ, {"PSWS_DATA_DIR": str(missing)}):
      options, message = self.parse("--station-dir", str(self.fallback))
    self.assertEqual(options["station_dir"], missing)
    self.assertEqual(message, "")
    with self.assertRaisesRegex(util.Error, "does not exist"):
      util.validate_station_dir(options["station_dir"])
