"""Hermetic tests for the Essentials 16.2 behavior installer (issue #16, M1).

No game required: a temp dir stands in for the target, another for the plugin
source library. Proves the honest install outcomes (present / missing / broken)
and that the loader assets are ensured.
"""

import types
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials162.behavior_install import has_plugin, install_behaviors
from chrooked_pokedex.report import ApplyReport

pytestmark = pytest.mark.unit


def _ruleset(*ids):
    """Minimal stand-in: the installer only reads ruleset.behaviors (id -> spec)."""
    return types.SimpleNamespace(behaviors={i: types.SimpleNamespace(chrooked_id=i) for i in ids})


def _source(tmp_path, plugins):
    """Build a plugin-source dir with loader assets + the given {id: contents}."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mkxp.json").write_text('{"preloadScript": ["Scripts/load_order_shim.rb"]}\n')
    (src / "load_order_shim.rb").write_text("# shim\n")
    for cid, contents in plugins.items():
        (src / f"chrooked_{cid}.rb").write_text(contents)
    return src


def _target(tmp_path):
    tgt = tmp_path / "game"
    (tgt / "Scripts").mkdir(parents=True)
    return tgt


def test_present_plugin_is_installed_and_reported(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\nputs 1\n"})
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("kindle"), report, source_dir=src)

    assert (tgt / "Scripts" / "chrooked_kindle.rb").read_text().startswith("# chrooked:kindle")
    installed = [e for e in report.entries if e.chrooked_id == "kindle"]
    assert len(installed) == 1
    assert installed[0].status == "applied"
    assert "installed" in installed[0].reason.lower()


def test_missing_plugin_is_noop_no_entry(tmp_path):
    src = _source(tmp_path, {})  # no plugin for this spec
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("someunported"), report, source_dir=src)

    assert not (tgt / "Scripts" / "chrooked_someunported.rb").exists()
    assert [e for e in report.entries if e.chrooked_id == "someunported"] == []


def test_empty_plugin_is_blocked_no_file(tmp_path):
    src = _source(tmp_path, {"broken": ""})  # empty source
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("broken"), report, source_dir=src)

    assert not (tgt / "Scripts" / "chrooked_broken.rb").exists()
    entry = next(e for e in report.entries if e.chrooked_id == "broken")
    assert entry.status == "blocked"


def test_mistagged_plugin_is_blocked(tmp_path):
    src = _source(tmp_path, {"wrong": "puts 'no tag here'\n"})  # missing # chrooked:wrong
    tgt = _target(tmp_path)
    report = ApplyReport()

    install_behaviors(tgt, _ruleset("wrong"), report, source_dir=src)

    assert not (tgt / "Scripts" / "chrooked_wrong.rb").exists()
    assert next(e for e in report.entries if e.chrooked_id == "wrong").status == "blocked"


def test_loader_assets_are_ensured(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\n"})
    tgt = _target(tmp_path)

    install_behaviors(tgt, _ruleset("kindle"), ApplyReport(), source_dir=src)

    assert (tgt / "mkxp.json").exists()
    assert (tgt / "Scripts" / "load_order_shim.rb").exists()


def test_has_plugin_requires_a_valid_plugin(tmp_path):
    # Q6 marker (HIGH#1): "ported" means a VALID plugin exists — not just any file —
    # so the create-reason never promises "installed" for one the installer rejects.
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\n", "empty": "", "wrong": "no tag\n"})
    assert has_plugin("kindle", source_dir=src) is True
    assert has_plugin("notported", source_dir=src) is False  # absent
    assert has_plugin("empty", source_dir=src) is False      # present but empty
    assert has_plugin("wrong", source_dir=src) is False      # present but mistagged


def test_idempotent_rerun_is_no_churn(tmp_path):
    src = _source(tmp_path, {"kindle": "# chrooked:kindle\nv=1\n"})
    tgt = _target(tmp_path)

    install_behaviors(tgt, _ruleset("kindle"), ApplyReport(), source_dir=src)
    report2 = ApplyReport()
    install_behaviors(tgt, _ruleset("kindle"), report2, source_dir=src)  # unchanged -> no-op

    assert (tgt / "Scripts" / "chrooked_kindle.rb").read_text() == "# chrooked:kindle\nv=1\n"
    # second run changed nothing -> emits no report line (mirrors the ability-edit no-churn pattern)
    assert [e for e in report2.entries if e.chrooked_id == "kindle"] == []
