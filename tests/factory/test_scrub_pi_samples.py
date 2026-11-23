from pathlib import Path

import pytest
from scrub_pi_samples import leftovers, main, scrub

SAMPLES = Path(__file__).parents[2] / "factory" / "samples" / "pi"

RAW = (
    '{"type":"session","id":"01a209f2-7eeb-72b1-b70b-5e8276c867fa"}\n'
    '{"id":"msg_011ChLSGSgJSkTuibnEfTosc","requestId":"req_011ChLSGSaqyMSqoE35oWZFJ",'
    '"responseId":"resp_08d7582e63cf5ff8016b049c64850887d280f172a9576c4d81",'
    '"utilization":0.43,"resetsAt":1795480800,"overageDisabledReason":"org_level_disabled",'
    '"text":"OK"}\n'
)


def test_ids_keep_prefix_and_length() -> None:
    out = scrub(RAW)
    assert '"id":"00000000-0000-0000-0000-000000000000"' in out
    assert '"id":"msg_' + "0" * 24 + '"' in out
    assert '"requestId":"req_' + "0" * 24 + '"' in out
    assert '"responseId":"resp_' + "0" * 50 + '"' in out


def test_account_usage_is_replaced() -> None:
    out = scrub(RAW)
    assert '"utilization":0,"resetsAt":0,"overageDisabledReason":"sample"' in out


def test_everything_else_is_unchanged() -> None:
    out = scrub(RAW)
    assert out.count("\n") == RAW.count("\n")
    assert '"type":"session"' in out
    assert '"text":"OK"' in out


def test_scrubbing_twice_changes_nothing() -> None:
    once = scrub(RAW)
    assert scrub(once) == once


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ('{"user":"someone@example.com"}', "email address"),
        ('{"key":"sk-ant-api03-abc"}', "Anthropic key or token"),
        ('{"key":"sk-proj-abcdefghijklmnopqrstuvwxyz"}', "OpenAI key"),
        ('{"auth":"Bearer abcdefghijklmnop"}', "bearer token"),
        ('{"jwt":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0"}', "JSON web token"),
    ],
)
def test_leftovers_are_named(text: str, found: str) -> None:
    assert found in leftovers(text)


def test_nothing_is_written_when_a_leftover_remains(tmp_path: Path) -> None:
    source, target = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    source.write_text('{"user":"someone@example.com"}\n', encoding="utf-8")
    assert main([str(source), str(target)]) == 1
    assert not target.exists()


def test_main_writes_the_scrubbed_copy(tmp_path: Path) -> None:
    source, target = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    source.write_text(RAW, encoding="utf-8")
    assert main([str(source), str(target)]) == 0
    assert target.read_text(encoding="utf-8") == scrub(RAW)


@pytest.mark.parametrize("name", ["claude.jsonl", "openai.jsonl"])
def test_committed_samples_are_scrubbed(name: str) -> None:
    text = (SAMPLES / name).read_text(encoding="utf-8")
    assert scrub(text) == text
    assert leftovers(text) == []
