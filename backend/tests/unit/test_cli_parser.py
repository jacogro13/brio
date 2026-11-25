from __future__ import annotations

from pathlib import Path

from chatbot.entrypoints.cli.parser import expand_references


def test_no_token_passthrough(tmp_path: Path) -> None:
    result = expand_references("just a plain message", tmp_path)
    assert result.content == "just a plain message"
    assert result.attachments == []
    assert result.skipped == []


def test_expands_file(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("greetings", encoding="utf-8")

    result = expand_references("read @hello.txt please", tmp_path)

    assert "```hello.txt" in result.content
    assert "greetings" in result.content
    assert len(result.attachments) == 1
    assert result.attachments[0].kind == "file"
    assert result.attachments[0].size_bytes == len("greetings")
    assert result.skipped == []


def test_strips_trailing_punctuation(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("x", encoding="utf-8")

    result = expand_references("look at @hello.txt.", tmp_path)

    assert "```hello.txt" in result.content
    assert result.content.rstrip().endswith(".")
    assert len(result.attachments) == 1


def test_rejects_path_outside_cwd(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        sub = tmp_path / "work"
        sub.mkdir()

        result = expand_references("read @../outside.txt", sub)

        assert "secret" not in result.content
        assert result.attachments == []
        assert len(result.skipped) == 1
        assert result.skipped[0][1] == "outside cwd"
    finally:
        outside.unlink(missing_ok=True)


def test_rejects_oversize(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("x" * 5000, encoding="utf-8")

    result = expand_references("@big.txt", tmp_path, max_bytes=100)

    assert "xxxx" not in result.content
    assert result.attachments == []
    assert len(result.skipped) == 1
    assert "too large" in result.skipped[0][1]


def test_rejects_binary(tmp_path: Path) -> None:
    bin_file = tmp_path / "blob.bin"
    bin_file.write_bytes(b"hello\x00world")

    result = expand_references("@blob.bin", tmp_path)

    assert result.attachments == []
    assert len(result.skipped) == 1
    assert result.skipped[0][1] == "binary file"


def test_rejects_missing(tmp_path: Path) -> None:
    result = expand_references("@nope.txt", tmp_path)

    assert result.attachments == []
    assert len(result.skipped) == 1
    assert result.skipped[0][1] == "not found"


def test_expands_directory(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "sub" / "b.txt").write_text("bb", encoding="utf-8")

    result = expand_references("@sub", tmp_path)

    assert "a.txt" in result.content
    assert "b.txt" in result.content
    assert len(result.attachments) == 1
    assert result.attachments[0].kind == "dir"


def test_multiple_tokens(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("AAA", encoding="utf-8")
    (tmp_path / "b.txt").write_text("BBB", encoding="utf-8")

    result = expand_references("compare @a.txt and @b.txt", tmp_path)

    assert "AAA" in result.content
    assert "BBB" in result.content
    assert len(result.attachments) == 2
