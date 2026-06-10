"""Regression tests for issue #14: 'charmap' codec errors on Windows.

The CLI must read and write UTF-8 regardless of the OS locale encoding, and
must not lose already-revised entries when a run fails partway through.
BibFixAgent is replaced with a fake so no API key or network is needed.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import bibfixer.cli as cli

REPO_ROOT = Path(__file__).resolve().parents[1]

UNICODE_BIB = (
    "@article{key1,\n"
    " author = {Łukasz Kałużny},\n"
    " title = {Cliché — naïve ćwiczenie},\n"
    " year = {2026},\n"
    "}\n"
    "\n"
    "@article{key2,\n"
    " author = {Jane Doe},\n"
    " title = {Plain Title},\n"
    " year = {2025},\n"
    "}\n"
)


@pytest.fixture
def fake_agent(monkeypatch):
    """Replace BibFixAgent in cli with a stub whose revise_bibtex is revise_fn."""

    def install(revise_fn):
        class FakeAgent:
            def __init__(self, **kwargs):
                pass

            def revise_bibtex(self, text, preferences):
                return revise_fn(text)

        monkeypatch.setattr(cli, "BibFixAgent", FakeAgent)

    return install


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["bibfixer", *argv])
    cli.main()


def test_reads_utf8_input_with_bom(tmp_path, monkeypatch, fake_agent):
    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_bytes(b"\xef\xbb\xbf" + UNICODE_BIB.encode("utf-8"))
    fake_agent(lambda text: text)

    run_cli(monkeypatch, "-i", str(in_file), "-o", str(out_file))

    content = out_file.read_bytes().decode("utf-8")
    assert not content.startswith("﻿")
    assert "Łukasz Kałużny" in content
    assert "key1" in content and "key2" in content


def test_output_is_utf8_even_when_not_representable_in_cp1252(
    tmp_path, monkeypatch, fake_agent
):
    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_text(UNICODE_BIB, encoding="utf-8")
    revised = "@article{key1,\n title = {Łódź — ćwiczenie},\n year = {2026},\n}"
    fake_agent(lambda text: revised)

    run_cli(monkeypatch, "-i", str(in_file), "-o", str(out_file))

    content = out_file.read_bytes().decode("utf-8")
    assert "Łódź — ćwiczenie" in content
    # the exact content that used to abort the whole run on Windows
    with pytest.raises(UnicodeEncodeError):
        content.encode("cp1252")


def test_partial_results_survive_midrun_crash(tmp_path, monkeypatch, fake_agent):
    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_text(UNICODE_BIB, encoding="utf-8")

    revised_first = "@article{key1,\n title = {Revised — Łukasz},\n year = {2026},\n}"
    calls = []

    def revise(text):
        calls.append(text)
        if len(calls) == 1:
            return revised_first
        raise KeyboardInterrupt  # not caught by the per-entry `except Exception`

    fake_agent(revise)

    with pytest.raises(KeyboardInterrupt):
        run_cli(monkeypatch, "-i", str(in_file), "-o", str(out_file))

    assert "Revised — Łukasz" in out_file.read_text(encoding="utf-8")


def test_parallel_workers_preserve_entry_order(tmp_path, monkeypatch, fake_agent):
    import time

    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_text(UNICODE_BIB, encoding="utf-8")

    def revise(text):
        # make entry 1 finish AFTER entry 2 to exercise out-of-order completion
        if "key1" in text:
            time.sleep(0.2)
        return text

    fake_agent(revise)

    run_cli(monkeypatch, "-i", str(in_file), "-o", str(out_file), "-w", "2")

    content = out_file.read_text(encoding="utf-8")
    assert content.index("key1") < content.index("key2")


def test_non_utf8_input_fails_with_clear_message(
    tmp_path, monkeypatch, fake_agent, capsys
):
    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_bytes("@article{key1,\n title = {café},\n}\n".encode("cp1252"))
    fake_agent(lambda text: text)

    with pytest.raises(SystemExit) as excinfo:
        run_cli(monkeypatch, "-i", str(in_file), "-o", str(out_file))

    assert excinfo.value.code == 1
    assert "UTF-8" in capsys.readouterr().err


def test_no_locale_dependent_file_io(tmp_path):
    """Run the CLI with -X warn_default_encoding: no open() in bibfixer may
    rely on the platform default encoding (the root cause of issue #14)."""
    in_file = tmp_path / "in.bib"
    out_file = tmp_path / "out.bib"
    in_file.write_text(UNICODE_BIB, encoding="utf-8")

    script = (
        "import sys\n"
        "import bibfixer.cli as cli\n"
        "class FakeAgent:\n"
        "    def __init__(self, **kwargs): pass\n"
        "    def revise_bibtex(self, text, preferences): return text\n"
        "cli.BibFixAgent = FakeAgent\n"
        f"sys.argv = ['bibfixer', '-i', {str(in_file)!r}, '-o', {str(out_file)!r}]\n"
        "cli.main()\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    bibfixer_warnings = [
        line
        for line in result.stderr.splitlines()
        if "EncodingWarning" in line and "bibfixer" in line
    ]
    assert not bibfixer_warnings, bibfixer_warnings
    assert "Łukasz" in out_file.read_text(encoding="utf-8")
