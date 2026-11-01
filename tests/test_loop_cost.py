"""Tests loop-detect + cost-tracker (adaptés de ctf-agent, MIT)."""

from fullctf.runner.loop_detect import detect_loop, LOOP_WARNING_MESSAGE
from fullctf.runner.cost_tracker import CostTracker


def test_detect_loop_flags_repeated_command():
    out = "\n".join(["cat /etc/passwd"] * 5 + ["ls -la", "whoami"])
    looped, cmd = detect_loop(out, min_repeat=4)
    assert looped and cmd == "cat /etc/passwd"


def test_detect_loop_none_when_varied():
    out = "cmd a\ncmd b\ncmd c\ncmd d\ncmd e"
    looped, cmd = detect_loop(out, min_repeat=4)
    assert not looped and cmd is None


def test_loop_warning_message_nonempty():
    assert "BOUCLE" in LOOP_WARNING_MESSAGE


def test_cost_tracker_records_effort_and_tokens():
    t = CostTracker()
    t.record("codex", 12.0, "…\ntokens used 8,170\n", found_flag=True)
    t.record("codex", 8.0, "rien", found_flag=False)
    t.record("claude", 600.0, "timeout")
    e = t.by_agent["codex"]
    assert e.attempts == 2 and e.seconds == 20.0 and e.tokens == 8170 and e.flags == 1
    assert t.by_agent["claude"].seconds == 600.0
    assert t.total_attempts == 3 and t.total_seconds == 620.0
    s = t.format_summary()
    assert "codex" in s and "claude" in s and "TOTAL" in s
