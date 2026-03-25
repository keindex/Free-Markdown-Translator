from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.cli.errors import present_cli_error


class PresentCliErrorTests(unittest.TestCase):
    def test_missing_api_key_is_user_friendly(self) -> None:
        presentation = present_cli_error(
            ValueError(
                "No API key available. Set provider.api_key in ~/.mdtx/config.yaml or "
                "set provider.api_key_env to an environment variable name."
            ),
            verbose=False,
        )
        self.assertIn("OpenAI API key is missing.", presentation.message)
        self.assertIn("provider.api_key", presentation.message)

    def test_file_not_found_is_user_friendly(self) -> None:
        presentation = present_cli_error(
            FileNotFoundError("Input path does not exist: missing.md"),
            verbose=False,
        )
        self.assertIn("Input file or directory was not found.", presentation.message)
        self.assertIn("missing.md", presentation.message)

    def test_no_input_files_matched_pattern_is_user_friendly(self) -> None:
        presentation = present_cli_error(
            ValueError("No input files matched pattern: *.markdown"),
            verbose=False,
        )
        self.assertIn("No Markdown files matched the current input rule.", presentation.message)
        self.assertIn("*.markdown", presentation.message)

    def test_unknown_error_suggests_verbose(self) -> None:
        presentation = present_cli_error(RuntimeError("boom"), verbose=False)
        self.assertIn("unexpected error", presentation.message.lower())
        self.assertIn("--verbose", presentation.message)

    def test_api_status_error_logs_provider_message(self) -> None:
        try:
            from openai import APIStatusError
        except ModuleNotFoundError:
            self.skipTest("openai package is not installed")

        response = Mock()
        response.request = Mock()
        exc = APIStatusError(
            "model service failed",
            response=response,
            body={"error": {"message": "quota exceeded"}},
        )

        with patch("src.cli.errors.logging.error") as mock_error:
            presentation = present_cli_error(exc, verbose=False)

        self.assertIn("HTTP", presentation.message)
        mock_error.assert_called_once_with(
            "Model service error details (HTTP %s): %s",
            exc.status_code,
            "quota exceeded",
        )


if __name__ == "__main__":
    unittest.main()
