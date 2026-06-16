"""ac4: the 16.2 dialect reuses the shared model/report/packet — it does not fork them.

Two proofs: (1) resolution imports `Ruleset` from the shared `chrooked_pokedex.model`,
and the foundation CLI path imports `ApplyReport` from `chrooked_pokedex.report`;
(2) a path scan asserts no copy of model.py / report.py / behavior packet lives under
appliers/essentials162/.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import chrooked_pokedex.model as shared_model
import chrooked_pokedex.report as shared_report
from chrooked_pokedex.appliers.essentials162 import resolution

_PKG = Path(resolution.__file__).parent
_FORBIDDEN = {"model.py", "report.py", "packet.py", "behavior.py"}


def test_resolution_imports_ruleset_from_shared_model():
    # The ResolutionMap builder takes the shared Ruleset, not a forked copy.
    assert resolution.Ruleset is shared_model.Ruleset


def test_cli_foundation_uses_shared_apply_report():
    from chrooked_pokedex import cli

    src = inspect.getsource(cli)
    assert "essentials162_resolution" in src
    # ApplyReport flows from the shared report module into the foundation path.
    assert cli.ApplyReport is shared_report.ApplyReport


def test_no_model_report_packet_copy_under_essentials162():
    offenders = [p.name for p in _PKG.iterdir() if p.name in _FORBIDDEN]
    assert offenders == [], f"essentials162 must not fork shared modules: {offenders}"
