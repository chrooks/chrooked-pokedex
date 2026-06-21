"""Per-mechanic harness scenarios — the only place that is mechanic-specific.

The harness *runner* (`harness.py`) is generic. Each mechanic contributes one
list of CHECKS here, aligned 1:1 and in order with that mechanic's
`test_cases` in `ruleset/behaviors/<id>.yaml`. A check says:

  * ``stage``  — the one human action that exercises this test_case in a debug
    battle (the play-one-battle step);
  * ``select`` — key/values that pick the relevant observation line the
    mechanic's plugin logged (``[chrooked:<id>] OBS k=v ...``);
  * ``expect`` — key/values that must hold on that observation for the case to
    pass.

Adding a mechanic = add an entry here + its plugin. The runner does not change.
Keys are arbitrary strings; they only have to agree with what the plugin logs,
so the runner stays mechanic-agnostic.
"""

from __future__ import annotations

# chrooked_id -> ordered checks, one per spec test_case.
SCENARIOS: dict[str, list[dict[str, object]]] = {
    "innerfocus": [
        {
            "stage": "With your Inner Focus user, use Focus Blast on the foe.",
            "select": {"move": "FOCUSBLAST", "if": "true"},
            "expect": {"result": "ALWAYS_HIT"},
        },
        {
            "stage": "With the SAME Inner Focus user, use Hydro Pump on the foe.",
            "select": {"move": "HYDROPUMP", "if": "true"},
            "expect": {"result": "NORMAL"},
        },
        {
            "stage": "Switch to a NON-Inner-Focus user and use Focus Blast on the foe.",
            "select": {"move": "FOCUSBLAST", "if": "false"},
            "expect": {"result": "NORMAL"},
        },
    ],
    "kindle": [
        {
            "stage": "With your Kindle user, use Flamethrower (Fire) on the foe.",
            "select": {"move": "FLAMETHROWER", "kindle": "true"},
            "expect": {"result": "BOOSTED"},
        },
        {
            # Spec names Surf; ANY non-Fire move witnesses "no boost" (Kindle only
            # touches Fire), so Tackle is an equally valid witness for this case.
            "stage": "With the SAME Kindle user, use a NON-Fire move (Surf, or Tackle) on the foe.",
            "select": {"move": "TACKLE", "kindle": "true"},
            "expect": {"result": "NORMAL"},
        },
        {
            "stage": "With the SAME Kindle user (at full HP), use Ember (Fire) on the foe.",
            "select": {"move": "EMBER", "kindle": "true"},
            "expect": {"result": "BOOSTED"},
        },
    ],
}
