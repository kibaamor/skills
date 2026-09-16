"""Bounded CommonMark-subset scanning for package-local resource pointers.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import PureWindowsPath

URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
COMMONMARK_BACKSLASH_ESCAPE_RE = re.compile(
    r"""\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])"""
)
MARKDOWN_STANDALONE_BLOCK_RE = re.compile(
    r"^[ \t]{0,3}(?:"
    r"#{1,6}(?:[ \t]+|$)|"
    r"(?:=+|-+)[ \t]*$|"
    r"(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$"
    r")"
)
MARKDOWN_LIST_ITEM_RE = re.compile(
    r"^(?P<indent> {0,3})"
    r"(?:(?P<bullet>[*+-])|(?P<number>\d{1,9})[.)])"
    r"(?P<spacing>[ \t]+|$)"
)
MARKDOWN_HTML_RAW_BLOCK_START_RE = re.compile(
    r"^<(?P<tag>script|pre|style|textarea)(?:[ \t]|>|$)", re.IGNORECASE
)
MARKDOWN_HTML_RAW_BLOCK_END_RES = {
    tag: re.compile(rf"</{tag}>", re.IGNORECASE)
    for tag in ("script", "pre", "style", "textarea")
}
MARKDOWN_HTML_DECLARATION_START_RE = re.compile(r"^<![A-Z]")
RESOURCE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.:/@?#=&%+-])(?<!\\)(?:\./)?"
    r"((?:scripts|references|assets|evals)/[A-Za-z0-9_./-]+)"
)
NONLOCAL_TOKEN_RE = re.compile(r"[^\s<>`]+")
URI_SCHEME_IN_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*:"
)


SHELL_FENCE_LANGUAGES = {
    "bash",
    "bat",
    "batch",
    "cmd",
    "console",
    "fish",
    "powershell",
    "ps1",
    "pwsh",
    "sh",
    "shell",
    "shell-session",
    "terminal",
    "zsh",
}
SESSION_FENCE_LANGUAGES = {"console", "shell-session", "terminal"}
POWERSHELL_FENCE_LANGUAGES = {"powershell", "ps1", "pwsh"}
SHELL_PROMPT_RE = re.compile(
    r"^\s*(?:PS(?:\s+[^>\r\n]*)?>|\\\\[^>\r\n]+>|[A-Za-z]:[\\/][^>\r\n]*>|"
    r"[^$>\r\n]+\$(?=[ \t])|[$>](?=[ \t]))[ \t]*",
    re.IGNORECASE,
)
SHELL_SCRIPT_CALL_RE = re.compile(
    r"^\s*@?(?:(?:call|source)\s+|[.&]\s+)?(?:sudo\s+)?(?:env\s+)?"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
    r"(?:(?:(?:python(?:3(?:\.\d+)?)?|py|bash|sh|zsh|fish|node|deno|"
    r"ruby|pwsh|powershell|cmd)(?:\.exe)?|uv(?:\.exe)?\s+run)"
    r"(?:\s+(?!['\"]?(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]"
    r"|%~dp0[\\/]?)?"
    r"(?:\.[\\/])?scripts[\\/])\S+){0,16}\s+)?"
    r"(?:"
    r'"(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]|%~dp0[\\/]?)?'
    r"(?:\.[\\/])?(?P<double_path>scripts[\\/][^\"\r\n]+)\"|"
    r"'(?:\.[\\/])?(?P<single_path>scripts[\\/][^'\r\n]+)'|"
    r"(?:\$(?:PSScriptRoot|\{PSScriptRoot\})[\\/]|%~dp0[\\/]?)?"
    r"(?:\.[\\/])?(?P<unquoted_path>scripts[\\/][A-Za-z0-9_.\\/-]+)"
    r")"
    r"(?=\s|$|[;&|])",
    re.IGNORECASE,
)


MAX_MARKDOWN_LINK_CANDIDATES = 4096
MAX_MARKDOWN_BRACKET_DEPTH = 4096
MAX_MARKDOWN_CODE_SPAN_DELIMITERS = 4096
MAX_MARKDOWN_CONTAINER_DEPTH = 256
MAX_MARKDOWN_TARGET_CHARACTERS = 1 << 20


@dataclass
class _MarkdownLinkCandidate:
    open_paren: int
    start: int
    angle: bool
    image: bool
    nested_candidate_start: int
    first_space: int | None = None
    close: int | None = None


@dataclass
class _MarkdownScanBudget:
    candidates: int = 0
    code_span_delimiters: int = 0
    target_characters: int = 0


class MarkdownScanLimitError(ValueError):
    """Raised when inline-link extraction exceeds a deterministic budget."""


def split_markdown_fences(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return non-fenced text and language-tagged fenced lines."""
    output: list[str] = []
    fenced_lines: list[tuple[str, str]] = []
    fence_character: str | None = None
    fence_length = 0
    fence_language = ""
    for line in text.splitlines():
        match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
        marker = match.group(1) if match else ""
        if fence_character is None and marker:
            fence_character = marker[0]
            fence_length = len(marker)
            info = match.group(2).strip()
            fence_language = info.split(maxsplit=1)[0].casefold() if info else ""
            output.append("")
            continue
        if (
            fence_character is not None
            and marker
            and marker[0] == fence_character
            and len(marker) >= fence_length
            and not match.group(2).strip()
        ):
            fence_character = None
            fence_length = 0
            fence_language = ""
            output.append("")
            continue
        if fence_character is None:
            output.append(line)
        else:
            output.append("")
            fenced_lines.append((fence_language, line))
    return "\n".join(output), fenced_lines


def markdown_link_target(raw_target: str) -> str:
    """Extract a Markdown link destination without confusing titles or URIs."""
    value = raw_target.strip()
    if value.startswith("<") and value.endswith(">"):
        target = value[1:-1]
    else:
        target = value.split(maxsplit=1)[0]
    return target


def commonmark_unescape(value: str) -> str:
    """Decode punctuation escapes that are valid in CommonMark destinations."""
    return COMMONMARK_BACKSLASH_ESCAPE_RE.sub(r"\1", value)


def commonmark_path(value: str) -> str:
    """Return the filesystem path part of a CommonMark link destination."""
    return commonmark_unescape(value).split("#", 1)[0]


def _append_markdown_target(
    targets: list[str],
    line: str,
    start: int,
    end: int,
    budget: _MarkdownScanBudget,
) -> None:
    target_length = end - start
    if budget.target_characters + target_length > MAX_MARKDOWN_TARGET_CHARACTERS:
        raise MarkdownScanLimitError(
            "Markdown link destinations exceed the "
            f"{MAX_MARKDOWN_TARGET_CHARACTERS}-character scan budget"
        )
    budget.target_characters += target_length
    targets.append(line[start:end])


def backslash_escape_mask(text: str) -> bytearray:
    """Mark characters preceded by an odd run of backslashes."""
    escaped = bytearray(len(text))
    preceding_backslashes = 0
    for index, character in enumerate(text):
        escaped[index] = preceding_backslashes % 2
        if character == "\\":
            preceding_backslashes += 1
        else:
            preceding_backslashes = 0
    return escaped


def _markdown_blockquote_prefix(text: str) -> tuple[int, int]:
    """Return the quote depth and content offset for one container line."""
    depth = 0
    position = 0
    while position < len(text):
        marker_start = position
        indentation = 0
        while (
            position < len(text)
            and text[position] == " "
            and indentation < 3
        ):
            position += 1
            indentation += 1
        if position >= len(text) or text[position] != ">":
            position = marker_start
            break
        position += 1
        if position < len(text) and text[position] in " \t":
            position += 1
        depth += 1
    return depth, position


def _markdown_html_block_terminator(
    text: str,
) -> str | re.Pattern[str] | None:
    """Return the CommonMark type 1-5 HTML block terminator, if any."""
    leading_whitespace = text[: len(text) - len(text.lstrip(" \t"))]
    if "\t" in leading_whitespace or len(leading_whitespace) > 3:
        return None
    text = text[len(leading_whitespace) :]
    raw_match = MARKDOWN_HTML_RAW_BLOCK_START_RE.match(text)
    if raw_match:
        return MARKDOWN_HTML_RAW_BLOCK_END_RES[raw_match.group("tag").casefold()]
    if text.startswith("<!--"):
        return "-->"
    if text.startswith("<?"):
        return "?>"
    if text.startswith("<![CDATA["):
        return "]]>"
    if MARKDOWN_HTML_DECLARATION_START_RE.match(text):
        return ">"
    return None


def _markdown_html_block_ended(
    terminator: str | re.Pattern[str], text: str
) -> bool:
    if isinstance(terminator, str):
        return terminator in text
    return terminator.search(text) is not None


def _mask_markdown_block(text: str) -> str:
    return "".join(character if character in "\r\n" else " " for character in text)


def _markdown_is_indented_code(text: str) -> bool:
    return text.startswith("\t") or text.startswith("    ")


def _without_inline_code_in_block(
    text: str, budget: _MarkdownScanBudget
) -> str:
    """Mask paired backtick spans within one Markdown text block."""
    escaped = backslash_escape_mask(text)

    runs: list[tuple[int, int, int]] = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        start = index
        index += 1
        while index < len(text) and text[index] == "`":
            index += 1
        budget.code_span_delimiters += 1
        if budget.code_span_delimiters > MAX_MARKDOWN_CODE_SPAN_DELIMITERS:
            raise MarkdownScanLimitError(
                "Markdown code-span delimiters exceed the "
                f"{MAX_MARKDOWN_CODE_SPAN_DELIMITERS}-run scan budget"
            )
        runs.append((start, index, index - start))

    next_matching = [-1] * len(runs)
    next_by_length: dict[int, int] = {}
    for run_index in range(len(runs) - 1, -1, -1):
        run_length = runs[run_index][2]
        next_matching[run_index] = next_by_length.get(run_length, -1)
        next_by_length[run_length] = run_index

    output = list(text)
    run_index = 0
    while run_index < len(runs):
        if escaped[runs[run_index][0]]:
            run_index += 1
            continue
        close_index = next_matching[run_index]
        if close_index == -1:
            run_index += 1
            continue
        start = runs[run_index][0]
        end = runs[close_index][1]
        for character_index in range(start, end):
            if output[character_index] not in "\r\n":
                output[character_index] = " "
        run_index = close_index + 1
    return "".join(output)


def without_inline_code(
    text: str, budget: _MarkdownScanBudget | None = None
) -> str:
    """Mask code spans and raw HTML within Markdown block boundaries."""
    budget = budget or _MarkdownScanBudget()
    output: list[str] = []
    block: list[str] = []
    active_quote_depth = 0
    active_list_indents: list[int] = []
    active_list_quote_depths: list[int] = []
    html_terminator: str | re.Pattern[str] | None = None
    html_quote_depth = 0
    html_list_indent = 0
    for line in text.splitlines(keepends=True):
        line = line.expandtabs(4)
        line_content = line.rstrip("\r\n")
        quote_depth, quote_offset = _markdown_blockquote_prefix(line_content)
        line_quote_depth = quote_depth
        quote_content = line_content[quote_offset:]
        quote_marker_indent = len(line_content) - len(line_content.lstrip(" "))

        if html_terminator is not None:
            html_leading_spaces = len(quote_content) - len(
                quote_content.lstrip(" \t")
            )
            if quote_depth != html_quote_depth or (
                html_list_indent and html_leading_spaces < html_list_indent
            ):
                html_terminator = None
                html_list_indent = 0
            else:
                output.append(_mask_markdown_block(line))
                if _markdown_html_block_ended(html_terminator, line_content):
                    html_terminator = None
                    html_list_indent = 0
                continue

        if not line.strip(" \t\r\n"):
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            output.append(line)
            active_quote_depth = 0
            active_list_indents.clear()
            active_list_quote_depths.clear()
            continue

        if active_quote_depth > quote_depth and MARKDOWN_LIST_ITEM_RE.match(
            quote_content
        ):
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            active_quote_depth = 0
            active_list_indents.clear()
            active_list_quote_depths.clear()

        quote_exits_list = bool(
            quote_depth
            and active_list_indents
            and quote_marker_indent < active_list_indents[-1]
            and quote_depth != active_list_quote_depths[-1]
        )
        if quote_exits_list:
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            active_quote_depth = 0
            retained_lists = bisect_right(active_list_indents, quote_marker_indent)
            del active_list_indents[retained_lists:]
            del active_list_quote_depths[retained_lists:]
        if quote_depth > active_quote_depth:
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            active_quote_depth = 0
        if quote_depth and not quote_content.strip(" \t"):
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            output.append(line)
            active_quote_depth = 0
            active_list_indents.clear()
            active_list_quote_depths.clear()
            continue

        if (
            block
            and active_quote_depth > quote_depth
            and active_list_quote_depths
            and active_quote_depth == active_list_quote_depths[-1]
            and _markdown_is_indented_code(quote_content)
        ):
            block.append(line)
            continue

        leading_spaces = len(quote_content) - len(quote_content.lstrip(" \t"))
        list_base_index = bisect_right(active_list_indents, leading_spaces) - 1
        list_base = (
            active_list_indents[list_base_index] if list_base_index >= 0 else 0
        )
        if active_list_indents and not list_base and not block:
            active_list_indents.clear()
            active_list_quote_depths.clear()
        block_content = quote_content[list_base:]

        inner_quote_depth, inner_quote_offset = _markdown_blockquote_prefix(
            block_content
        )
        if inner_quote_depth:
            line_quote_depth += inner_quote_depth
            if block and line_quote_depth > active_quote_depth:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            block_content = block_content[inner_quote_offset:]

        if _markdown_is_indented_code(block_content) and not block:
            output.append(_mask_markdown_block(line))
            active_quote_depth = 0
            if not list_base:
                active_list_indents.clear()
                active_list_quote_depths.clear()
            continue

        if MARKDOWN_STANDALONE_BLOCK_RE.match(block_content):
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            output.append(_without_inline_code_in_block(line, budget))
            active_quote_depth = 0
            if not list_base:
                active_list_indents.clear()
                active_list_quote_depths.clear()
            continue

        new_html_terminator = _markdown_html_block_terminator(block_content)
        if new_html_terminator is not None:
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()
            output.append(_mask_markdown_block(line))
            if not _markdown_html_block_ended(new_html_terminator, block_content):
                html_terminator = new_html_terminator
                html_quote_depth = line_quote_depth
                html_list_indent = list_base
            active_quote_depth = 0
            if not list_base:
                active_list_indents.clear()
                active_list_quote_depths.clear()
            continue

        list_match = MARKDOWN_LIST_ITEM_RE.match(block_content)
        starts_list_item = False
        item_content = ""
        spacing = ""
        padding = 1
        if list_match:
            spacing = list_match.group("spacing")
            unpadded_content = block_content[list_match.end() :]
            item_has_content = bool(unpadded_content.strip(" \t"))
            padding = (
                len(spacing)
                if item_has_content and 1 <= len(spacing) <= 4
                else 1
            )
            item_content = block_content[
                list_match.start("spacing") + padding :
            ]
            ordered_start = list_match.group("number")
            can_interrupt = item_has_content and (
                list_match.group("bullet") is not None
                or (ordered_start is not None and int(ordered_start) == 1)
            )
            starts_existing_list_item = bool(active_list_indents) and (
                not list_base or list_base < active_list_indents[-1]
            )
            starts_list_item = not block or starts_existing_list_item or can_interrupt
        if starts_list_item:
            if block:
                output.append(
                    _without_inline_code_in_block("".join(block), budget)
                )
                block.clear()

            new_content_indent = list_base + list_match.start("spacing") + padding
            if list_base:
                retained_lists = bisect_right(active_list_indents, list_base)
                del active_list_indents[retained_lists:]
                del active_list_quote_depths[retained_lists:]
            else:
                active_list_indents.clear()
                active_list_quote_depths.clear()
            if (
                not active_list_indents
                or active_list_indents[-1] != new_content_indent
            ):
                if len(active_list_indents) >= MAX_MARKDOWN_CONTAINER_DEPTH:
                    raise MarkdownScanLimitError(
                        "Markdown container nesting exceeds the "
                        f"{MAX_MARKDOWN_CONTAINER_DEPTH}-level scan budget"
                    )
                active_list_indents.append(new_content_indent)
                active_list_quote_depths.append(line_quote_depth)

            item_inner_quote_depth, item_inner_quote_offset = (
                _markdown_blockquote_prefix(item_content)
            )
            if item_inner_quote_depth:
                line_quote_depth += item_inner_quote_depth
                item_content = item_content[item_inner_quote_offset:]
            if _markdown_is_indented_code(item_content):
                output.append(_mask_markdown_block(line))
                active_quote_depth = 0
                continue
            if MARKDOWN_STANDALONE_BLOCK_RE.match(item_content):
                output.append(_without_inline_code_in_block(line, budget))
                active_quote_depth = 0
                continue
            new_html_terminator = _markdown_html_block_terminator(item_content)
            if new_html_terminator is not None:
                output.append(_mask_markdown_block(line))
                if not _markdown_html_block_ended(
                    new_html_terminator, item_content
                ):
                    html_terminator = new_html_terminator
                    html_quote_depth = line_quote_depth
                    html_list_indent = new_content_indent
                active_quote_depth = 0
                continue

        if not block:
            active_quote_depth = line_quote_depth
        block.append(line)

    if block:
        output.append(_without_inline_code_in_block("".join(block), budget))
    return "".join(output)


def without_nonlocal_tokens(text: str) -> str:
    """Mask URI and email-like tokens before scanning bare package paths."""
    output = list(text)
    for match in NONLOCAL_TOKEN_RE.finditer(text):
        token = match.group()
        at_index = token.find("@", 1)
        if at_index != -1 and at_index < len(token) - 1:
            start = match.start()
        else:
            scheme = URI_SCHEME_IN_TOKEN_RE.search(token)
            if scheme is None:
                continue
            start = match.start() + scheme.start()
        output[start : match.end()] = " " * (match.end() - start)
    return "".join(output)


def _markdown_link_targets_on_line(
    line: str, budget: _MarkdownScanBudget
) -> list[str]:
    """Preserve the supported inline-link subset in output-sensitive linear time."""
    length = len(line)
    escaped = backslash_escape_mask(line)
    candidates: list[_MarkdownLinkCandidate] = []

    # Find inline links and image targets without repeatedly scanning suffixes.
    bracket_stack: list[tuple[bool, int]] = []
    index = 0
    while index < length:
        if escaped[index]:
            index += 1
            continue
        character = line[index]
        if character == "[":
            if len(bracket_stack) >= MAX_MARKDOWN_BRACKET_DEPTH:
                raise MarkdownScanLimitError(
                    "Markdown bracket nesting exceeds the "
                    f"{MAX_MARKDOWN_BRACKET_DEPTH}-level scan budget"
                )
            image = index > 0 and line[index - 1] == "!" and not escaped[index - 1]
            bracket_stack.append((image, len(candidates)))
        elif character == "]" and bracket_stack:
            image, nested_candidate_start = bracket_stack.pop()
            if index + 1 < length and line[index + 1] == "(":
                budget.candidates += 1
                if budget.candidates > MAX_MARKDOWN_LINK_CANDIDATES:
                    raise MarkdownScanLimitError(
                        "Markdown link candidates exceed the "
                        f"{MAX_MARKDOWN_LINK_CANDIDATES}-candidate scan budget"
                    )
                open_paren = index + 1
                start = open_paren + 1
                while start < length and line[start] in " \t":
                    start += 1
                candidates.append(
                    _MarkdownLinkCandidate(
                        open_paren=open_paren,
                        start=start,
                        angle=start < length and line[start] == "<",
                        image=image,
                        nested_candidate_start=nested_candidate_start,
                    )
                )
                index += 1
        index += 1

    if not candidates:
        return []

    by_open_paren = {candidate.open_paren: candidate for candidate in candidates}
    parenthesis_stack: list[int] = []
    for index, character in enumerate(line):
        if escaped[index]:
            continue
        if character == "(":
            parenthesis_stack.append(index)
        elif character in " \t":
            if parenthesis_stack:
                candidate = by_open_paren.get(parenthesis_stack[-1])
                if (
                    candidate is not None
                    and not candidate.angle
                    and index >= candidate.start
                    and candidate.first_space is None
                ):
                    candidate.first_space = index
        elif character == ")" and parenthesis_stack:
            open_paren = parenthesis_stack.pop()
            candidate = by_open_paren.get(open_paren)
            if candidate is not None:
                candidate.close = index

    next_gt = [-1] * (length + 1)
    next_close = [-1] * (length + 1)
    nearest_gt = -1
    nearest_close = -1
    for index in range(length - 1, -1, -1):
        if not escaped[index]:
            if line[index] == ">":
                nearest_gt = index
            if line[index] == ")":
                nearest_close = index
        next_gt[index] = nearest_gt
        next_close[index] = nearest_close

    targets: list[str] = []
    exposed_links: list[int] = []
    for candidate_index, candidate in enumerate(candidates):
        target_end: int | None = None
        if candidate.start >= length:
            continue
        elif candidate.angle:
            end = next_gt[candidate.start + 1]
            if end != -1 and next_close[end + 1] != -1:
                target_end = end + 1
        elif candidate.first_space is not None:
            if next_close[candidate.first_space + 1] != -1:
                target_end = candidate.first_space
        elif candidate.close is not None:
            target_end = candidate.close

        contains_link = bool(
            exposed_links
            and exposed_links[-1] >= candidate.nested_candidate_start
        )
        valid = target_end is not None and (candidate.image or not contains_link)
        if valid:
            _append_markdown_target(
                targets, line, candidate.start, target_end, budget
            )
            if candidate.image:
                while (
                    exposed_links
                    and exposed_links[-1] >= candidate.nested_candidate_start
                ):
                    exposed_links.pop()
            else:
                exposed_links.append(candidate_index)
    return targets


def markdown_link_targets(text: str) -> list[str]:
    """Extract inline-link destinations without repeatedly scanning suffixes."""
    budget = _MarkdownScanBudget()
    text = without_inline_code(text, budget)
    targets: list[str] = []
    line_start = 0
    for index, character in enumerate(text):
        if character in "\r\n":
            targets.extend(
                _markdown_link_targets_on_line(text[line_start:index], budget)
            )
            line_start = index + 1
    targets.extend(_markdown_link_targets_on_line(text[line_start:], budget))
    return targets


def shell_script_path(language: str, line: str) -> str | None:
    """Return a package script invoked by one shell-fence command line."""
    prompt_match = SHELL_PROMPT_RE.match(line)
    if language in SESSION_FENCE_LANGUAGES and prompt_match is None:
        return None
    command = line[prompt_match.end() :] if prompt_match else line
    stripped = command.lstrip()
    if (
        not stripped
        or stripped.startswith(("#", "::"))
        or re.match(r"(?i)^@?rem(?:\s|$)", stripped)
    ):
        return None
    powershell_prompt = bool(
        language in SESSION_FENCE_LANGUAGES
        and re.match(r"^\s*PS(?:\s+[^>\r\n]*)?>", line, re.IGNORECASE)
    )
    if (
        language in POWERSHELL_FENCE_LANGUAGES or powershell_prompt
    ) and stripped.startswith(("'", '"')):
        return None
    match = SHELL_SCRIPT_CALL_RE.match(command)
    if match is None:
        return None
    path = next(
        value
        for value in (
            match.group("double_path"),
            match.group("single_path"),
            match.group("unquoted_path"),
        )
        if value is not None
    )
    return path.replace("\\", "/")


def extract_paths(text: str) -> dict[str, bool]:
    """Map resource paths to whether a real Markdown pointer requires them."""
    instruction_text, fenced_lines = split_markdown_fences(text)
    bare_text = without_nonlocal_tokens(instruction_text)
    paths: dict[str, bool] = {}
    for match in RESOURCE_PATH_RE.finditer(bare_text):
        path = match.group(1)
        if path.rsplit("/", 1)[-1].strip("."):
            path = path.rstrip(".")
        paths[path] = False
    for language, line in fenced_lines:
        if language not in SHELL_FENCE_LANGUAGES:
            continue
        script_path = shell_script_path(language, line)
        if script_path:
            paths[script_path] = False
    for raw_target in markdown_link_targets(instruction_text):
        target = markdown_link_target(raw_target)
        comparison_target = commonmark_path(target)
        windows_target = PureWindowsPath(comparison_target)
        if comparison_target and (
            windows_target.drive
            or windows_target.root
            or not URI_SCHEME_RE.match(comparison_target)
        ):
            paths[target] = True
    return paths
