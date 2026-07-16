"""Line-surgical splice helpers for RGBDS macro tables.

The only edit primitive here is: find the one macro line to change, rewrite
selected comma-separated args in place preserving column alignment, and leave
every other byte of the file alone — the same philosophy as essentials162's
byte-faithful PBS splice, so target diffs stay reviewable.
"""

from __future__ import annotations

import re

# Branch labels for a line's position relative to FAITHFUL conditionals.
# "nonfaithful" covers both an `else` after `if DEF(FAITHFUL)` and the first
# branch of `if !DEF(FAITHFUL)` — the branches Chris's rebalance owns.
UNCONDITIONAL = "unconditional"
FAITHFUL = "faithful"
NONFAITHFUL = "nonfaithful"

_IF_FAITHFUL = re.compile(r"^\s*if\s+DEF\(FAITHFUL\)")
_IF_NOT_FAITHFUL = re.compile(r"^\s*if\s+!DEF\(FAITHFUL\)")


def classify_lines(lines: list[str]) -> list[str]:
    """Label every line with its FAITHFUL branch state.

    Conditionals are tracked as a stack so an unrelated nested `if` (a feature
    flag inside a FAITHFUL block) cannot flip or close the FAITHFUL state.
    """
    labels = []
    stack: list[str] = []  # frames: FAITHFUL / NONFAITHFUL / "" (unrelated if)
    for line in lines:
        stripped = line.strip()
        if _IF_FAITHFUL.match(line):
            stack.append(FAITHFUL)
        elif _IF_NOT_FAITHFUL.match(line):
            stack.append(NONFAITHFUL)
        elif stripped.startswith("if "):
            stack.append("")
        elif stripped == "else" and stack:
            if stack[-1] == FAITHFUL:
                stack[-1] = NONFAITHFUL
            elif stack[-1] == NONFAITHFUL:
                stack[-1] = FAITHFUL
        elif stripped == "endc" and stack:
            stack.pop()
        faithful_frames = [frame for frame in stack if frame]
        labels.append(faithful_frames[-1] if faithful_frames else UNCONDITIONAL)
    return labels


def find_macro_line(lines: list[str], macro: str, symbol: str) -> int | None:
    """Index of the editable `\\t<macro> <SYMBOL>,` line.

    When the symbol appears in a FAITHFUL conditional, the non-faithful branch
    line is returned (the FAITHFUL build stays honest). Every FAITHFUL block in
    a fixed-size table carries both branches, so a match in the faithful branch
    always has a non-faithful sibling.
    """
    labels = classify_lines(lines)
    prefix = f"\t{macro} {symbol},"
    for index, line in enumerate(lines):
        if line.startswith(prefix) and labels[index] != FAITHFUL:
            return index
    return None


def splice_args(line: str, replacements: dict[int, str]) -> str:
    """Rewrite 1-indexed comma-separated args of a macro line in place.

    Numeric values are right-aligned into the old field width; symbol values
    are left-aligned and the following field's padding absorbs the length
    delta, so comma columns stay put for the rest of the line.
    """
    segments = line.split(",")
    carry = 0  # width delta to absorb into the next segment's leading spaces
    for index in range(1, len(segments)):
        old = segments[index]
        body = old.lstrip(" ")
        pad = len(old) - len(body)
        pad = max(1, pad - carry)
        carry = 0
        argnum = index + 1  # segment 0 holds the macro name + arg 1
        if argnum not in replacements:
            segments[index] = " " * pad + body
            continue
        # A trailing `; comment` is not part of the value — preserve it verbatim.
        comment = ""
        match = re.search(r"\s*;.*$", body)
        if match:
            comment = match.group(0)
            body = body[: match.start()]
        new = replacements[argnum]
        if re.fullmatch(r"-?\d+", new):
            # Right-align into the old field, always keeping one leading space.
            width = max(pad + len(body), len(new) + 1)
            segments[index] = f"{new:>{width}}" + comment
        else:
            # Keep the field's original left padding; the next field's padding
            # absorbs any length difference so later commas stay aligned.
            segments[index] = " " * pad + new + comment
            carry = len(new) - len(body)
    return ",".join(segments)
