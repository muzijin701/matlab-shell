"""Tests for multiline auto-continuation and tiered Tab completion."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from matlab_shell.completer import MatlabCompleter
from matlab_shell.multiline import is_complete_statement


def test_multiline_complete_and_incomplete_cases() -> None:
    # Complete single-line statements
    assert is_complete_statement("") is True
    assert is_complete_statement("   ") is True
    assert is_complete_statement("x = 1 + 2;") is True
    assert is_complete_statement("!dir") is True
    assert is_complete_statement(".help") is True
    assert is_complete_statement(".5 + 1") is True

    # Indexing `end` inside brackets must NOT break block tracking
    assert is_complete_statement("y = a(1:end);") is True
    assert is_complete_statement("for i = 1:3\n  y = a(1:end);\nend") is True
    assert is_complete_statement("for i = 1:3\n  y = a(1:end);") is False

    # Nested blocks
    assert is_complete_statement("if x > 0\n  for k = 1:3\n    disp(k)\n  end") is False
    assert is_complete_statement("if x > 0\n  for k = 1:3\n    disp(k)\n  end\nend") is True
    assert is_complete_statement("function y = f(x)\n  y = x + 1;\nend") is True
    assert is_complete_statement("classdef Foo\n  methods\n    function m()\n    end\n  end") is False
    assert is_complete_statement("classdef Foo\n  methods\n    function m()\n    end\n  end\nend") is True

    # Brackets
    assert is_complete_statement("A = [1, 2;") is False
    assert is_complete_statement("A = [1, 2;\n 3, 4]") is True
    assert is_complete_statement("f(1, {2") is False
    assert is_complete_statement("f(1, {2})") is True

    # Ellipsis continuation (including trailing comment after ...)
    assert is_complete_statement("x = 1 + ...") is False
    assert is_complete_statement("x = 1 + ... % comment\n 2;") is True

    # Comments and string literals must not trigger blocks
    assert is_complete_statement("% for if while function") is True
    assert is_complete_statement("s = 'for if function';") is True
    assert is_complete_statement('s = "for if classdef";') is True
    assert is_complete_statement("%{\nfor i = 1:3") is False
    assert is_complete_statement("%{\nfor i = 1:3\n%}\nx = 1;") is True
    assert is_complete_statement("B = A' * A;") is True


def test_tiered_tab_completion(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "my_solver.m").write_text("x = 1;\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hi\n", encoding="utf-8")

    completer = MatlabCompleter(
        get_workspace_vars=lambda: ["my_var", "my_matrix", "disp"],
        get_cwd=lambda: tmp_path,
    )
    event = CompleteEvent(completion_requested=True)

    # Tier 1: Meta-Commands
    meta_texts = [c.text for c in completer.get_completions(Document(".s"), event)]
    assert meta_texts == [".sessions"]
    all_meta = [c.text for c in completer.get_completions(Document("."), event)]
    assert ".help" in all_meta and ".exit" in all_meta

    # Tier 2: Path inside quotes and after `!`
    quote_texts = [c.text for c in completer.get_completions(Document("run('my_"), event)]
    assert quote_texts == ["my_solver.m"]

    dir_texts = [c.text for c in completer.get_completions(Document("!type sub"), event)]
    assert dir_texts == ["subdir/"]

    # Tier 3: Workspace vars + local .m stems + MATLAB keywords (deduplicated)
    code_texts = [c.text for c in completer.get_completions(Document("x = my_"), event)]
    assert code_texts == ["my_var", "my_matrix", "my_solver"]

    disp_texts = [c.text for c in completer.get_completions(Document("di"), event)]
    assert disp_texts.count("disp") == 1
