from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automouse.config import RConfig
from automouse.exceptions import RTranslationError
from automouse.r_runner import run_r_translation


class RRunnerTests(unittest.TestCase):
    def _config(self, directory: Path, timeout: int = 3) -> RConfig:
        executable = directory / "Rscript"
        wrapper = directory / "wrapper.R"
        translation = directory / "translation.R"
        for path in (executable, wrapper, translation):
            path.write_text("fixture", encoding="utf-8")
        return RConfig(executable, translation, wrapper, timeout, False)

    def test_successful_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            source = directory / "input.csv"
            source.write_text("Sample,Strain,G12D mut\nCM1,Kras,+-\n", encoding="utf-8")
            output = directory / "output.csv"

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                output.write_text("Sample,Genotype\nCM1,K/+\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with patch("automouse.r_runner.subprocess.run", side_effect=fake_run) as mocked:
                result = run_r_translation(source, output, config)
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(mocked.call_args.kwargs["shell"])
            self.assertIn("--input", result.command)
            self.assertIn("--output", result.command)

    def test_nonzero_exit_code_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            output = directory / "output.csv"
            completed = subprocess.CompletedProcess([], 7, "", "bad assay")
            with patch("automouse.r_runner.subprocess.run", return_value=completed):
                with self.assertRaisesRegex(RTranslationError, "exit code 7"):
                    run_r_translation(source, output, config)

    def test_timeout_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory, timeout=1)
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            output = directory / "output.csv"
            with patch(
                "automouse.r_runner.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["Rscript"], 1),
            ):
                with self.assertRaisesRegex(RTranslationError, "timed out"):
                    run_r_translation(source, output, config)

    def test_missing_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            output = directory / "output.csv"
            completed = subprocess.CompletedProcess([], 0, "ok", "")
            with patch("automouse.r_runner.subprocess.run", return_value=completed):
                with self.assertRaisesRegex(RTranslationError, "did not create"):
                    run_r_translation(source, output, config)

    def test_empty_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            output = directory / "output.csv"

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                output.write_bytes(b"")
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with patch("automouse.r_runner.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(RTranslationError, "empty output"):
                    run_r_translation(source, output, config)

    def test_missing_executable_fails_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            config.executable.unlink()
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(RTranslationError, "executable not found"):
                run_r_translation(source, directory / "output.csv", config)

    def test_missing_translation_script_fails_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            config = self._config(directory)
            config.translation_script.unlink()
            source = directory / "input.csv"
            source.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(RTranslationError, "script not found"):
                run_r_translation(source, directory / "output.csv", config)


if __name__ == "__main__":
    unittest.main()
