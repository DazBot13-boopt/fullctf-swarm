"""Tests du cerveau LLM du Commander + moteur Attack/Defense."""

from fullctf.agents import AgentRegistry, MockAgentAdapter
from fullctf.attackdefense import ADFlag, ADSubmitResult, AttackDefenseBot
from fullctf.commander import Commander, CommanderBrain
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.mission import AgentProvider


# --- Cerveau LLM du Commander ---

def _agents():
    reg = AgentRegistry()
    reg.register(MockAgentAdapter(AgentProvider.CODEX))
    return reg


def test_brain_classifies_from_llm_answer():
    adapter = MockAgentAdapter(AgentProvider.CLAUDE, response="C'est clairement du crypto")
    brain = CommanderBrain(adapter)
    cat = brain.classify(Challenge(title="???"), fallback=Category.MISC)
    assert cat == Category.CRYPTO


def test_brain_falls_back_on_unparseable():
    adapter = MockAgentAdapter(AgentProvider.CLAUDE, response="aucune idée franchement")
    brain = CommanderBrain(adapter)
    cat = brain.classify(Challenge(title="x"), fallback=Category.MISC)
    assert cat == Category.MISC


def test_brain_falls_back_on_failure():
    adapter = MockAgentAdapter(AgentProvider.CLAUDE, succeed=False)
    brain = CommanderBrain(adapter)
    assert brain.classify(Challenge(title="x"), fallback=Category.WEB) == Category.WEB


def test_commander_uses_brain_only_when_rules_uncertain():
    # Règles sûres (catégorie explicite) -> le cerveau n'intervient pas.
    adapter = MockAgentAdapter(AgentProvider.CLAUDE, response="pwn")
    cmd = Commander(_agents(), brain=CommanderBrain(adapter))
    c = Challenge(title="x", category=Category.WEB, difficulty=Difficulty.EASY)
    plan = cmd.plan(c)
    assert plan.category == "web"  # le cerveau n'a pas écrasé la règle


def test_commander_invokes_brain_when_misc():
    adapter = MockAgentAdapter(AgentProvider.CLAUDE, response="reverse engineering challenge")
    cmd = Commander(_agents(), brain=CommanderBrain(adapter))
    # Pas de catégorie, pas d'indice -> règles donnent MISC -> cerveau appelé.
    c = Challenge(title="mystery", description="no obvious hints", difficulty=Difficulty.HARD)
    plan = cmd.plan(c)
    assert plan.category == "reverse"


# --- Attack/Defense bot ---

class _ADSub:
    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.calls = []

    def submit(self, flag):
        self.calls.append(flag)
        return self.verdicts.get(flag, ADSubmitResult.ACCEPTED)


def test_ad_dedup_and_flush():
    sub = _ADSub({"B{2}": ADSubmitResult.REJECTED})
    bot = AttackDefenseBot(sub)
    assert bot.enqueue(ADFlag(value="A{1}")) is True
    assert bot.enqueue(ADFlag(value="B{2}")) is True
    assert bot.enqueue(ADFlag(value="A{1}")) is False  # doublon
    assert bot.pending() == 2

    stats = bot.flush()
    assert stats.submitted == 2
    assert stats.accepted == 1
    assert stats.rejected == 1
    assert stats.duplicates_skipped == 1
    assert bot.pending() == 0
    assert sub.calls == ["A{1}", "B{2}"]


def test_ad_handles_expired_and_errors():
    sub = _ADSub({"X{1}": ADSubmitResult.EXPIRED, "Y{2}": ADSubmitResult.ERROR})
    bot = AttackDefenseBot(sub)
    bot.enqueue(ADFlag(value="X{1}", round=1))
    bot.enqueue(ADFlag(value="Y{2}", round=1))
    stats = bot.flush()
    assert stats.expired == 1
    assert stats.errors == 1
