import asyncio
from agents.base_agent import Agent

ATTACK_TIMEOUT = 90  # seconds per agent before giving up

PRESET_QUESTIONS = [
    "国库亏空，仅剩三百万两白银，如何在一年内充实国库？",
    "北疆异族大举入侵，边境十城告急，如何以最小代价平定战局？",
    "江南连年水患，百万流民涌入京城，民怨沸腾，如何安置？",
    "科举舞弊案震惊朝野，寒门学子聚集午门请愿，如何处置？",
    "皇上有意削藩，如何在不引发内乱的前提下推进？",
    "西洋传教士带来奇技淫巧，是闭关锁国还是开放通商？",
    "太后病危，朝中两派争夺监国之权，如何稳定局势？",
]

SEP = "=" * 60


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_proposals(proposals: dict[str, str]) -> str:
    return "\n\n".join(f"【{name}的方案】\n{text}" for name, text in proposals.items())


def _fmt_attacks(attacks: dict[str, str]) -> str:
    return "\n\n".join(f"【{name}的攻击】\n{text}" for name, text in attacks.items())


# ── phases ───────────────────────────────────────────────────────────────────

def select_question() -> str:
    print(f"\n{SEP}")
    print("【皇上出题】请选择本轮议题：")
    print(SEP)
    for i, q in enumerate(PRESET_QUESTIONS, 1):
        print(f"  {i}. {q}")
    print(f"  {len(PRESET_QUESTIONS) + 1}. 自定义题目")
    print(SEP)

    raw = input("请输入选项编号（或直接输入自定义题目）：").strip()

    try:
        idx = int(raw)
        if 1 <= idx <= len(PRESET_QUESTIONS):
            return PRESET_QUESTIONS[idx - 1]
        if idx == len(PRESET_QUESTIONS) + 1:
            return input("请输入题目：").strip()
    except ValueError:
        if raw:
            return raw

    return PRESET_QUESTIONS[0]


async def run_proposal_phase(alive: list[Agent], question: str) -> dict[str, str]:
    print(f"\n{SEP}")
    print("【第一阶段：提案】各皇子同时提交方案……")
    print(SEP)

    prompt = f"皇上今日出题：{question}\n\n请提交你的施政方案。"
    results = await asyncio.gather(*[agent.execute(prompt) for agent in alive])

    proposals = dict(zip([a.name for a in alive], results))
    for name, text in proposals.items():
        print(f"\n  ▶ 【{name}】\n{text}")
    return proposals


async def run_attack_phase(
    alive: list[Agent], proposals: dict[str, str], timeout: int = ATTACK_TIMEOUT
) -> dict[str, str]:
    print(f"\n{SEP}")
    print(f"【第二阶段：攻击】各皇子互相攻击（每人限时 {timeout} 秒）……")
    print(SEP)

    proposal_ctx = _fmt_proposals(proposals)

    async def _attack(agent: Agent) -> str:
        others = ", ".join(n for n in proposals if n != agent.name)
        prompt = (
            f"本轮各皇子方案如下：\n\n{proposal_ctx}\n\n"
            f"现在是攻击阶段。请选择以上方案中你认为最应该被淘汰的一位皇子，"
            f"指出其方案最致命的漏洞。攻击目标必须是以下之一：{others}。"
            f"\n先点名攻击目标，再展开论述。"
        )
        try:
            return await asyncio.wait_for(agent.execute(prompt), timeout=timeout)
        except asyncio.TimeoutError:
            return "（超时未回应）"

    results = await asyncio.gather(*[_attack(a) for a in alive])
    attacks = dict(zip([a.name for a in alive], results))

    for name, text in attacks.items():
        print(f"\n  ⚔ 【{name}的攻击】\n{text}")
    return attacks


async def run_vote_phase(
    alive: list[Agent], proposals: dict[str, str], attacks: dict[str, str]
) -> str:
    print(f"\n{SEP}")
    print("【第三阶段：投票】各皇子同时投票淘汰……")
    print(SEP)

    ctx = (
        f"本轮方案回顾：\n{_fmt_proposals(proposals)}\n\n"
        f"攻击回顾：\n{_fmt_attacks(attacks)}"
    )

    async def _vote(agent: Agent) -> str:
        others = [n for n in [a.name for a in alive] if n != agent.name]
        prompt = (
            f"{ctx}\n\n"
            f"现在进行淘汰投票。你必须投票淘汰一人，不能投自己。"
            f"候选人：{', '.join(others)}\n\n"
            f"只回答被淘汰者的名字，不需要任何解释。"
        )
        response = await agent.execute(prompt)
        for name in others:
            if name in response:
                return name
        return others[0]  # fallback if model doesn't include a valid name

    results = await asyncio.gather(*[_vote(a) for a in alive])
    vote_map = dict(zip([a.name for a in alive], results))

    tally: dict[str, int] = {a.name: 0 for a in alive}
    print()
    for voter, target in vote_map.items():
        tally[target] += 1
        print(f"  {voter} 投票淘汰 → {target}")

    eliminated = max(tally, key=lambda k: tally[k])
    print(f"\n  【结果】{eliminated} 得 {tally[eliminated]} 票，被淘汰！")
    return eliminated


# ── round + game loop ────────────────────────────────────────────────────────

async def run_round(agents: list[Agent], round_num: int) -> str:
    alive = [a for a in agents if a.alive]

    print(f"\n{'#' * 60}")
    print(f"  第 {round_num} 轮  |  存活：{', '.join(a.name for a in alive)}")
    print(f"{'#' * 60}")

    question = select_question()
    proposals = await run_proposal_phase(alive, question)
    attacks = await run_attack_phase(alive, proposals)
    eliminated = await run_vote_phase(alive, proposals, attacks)

    for a in agents:
        if a.name == eliminated:
            a.alive = False
            break

    return eliminated


async def run_game(agents: list[Agent]) -> None:
    print(f"\n{'#' * 60}")
    print("  九子夺嫡  —  游戏开始")
    print(f"{'#' * 60}")

    round_num = 1
    while sum(1 for a in agents if a.alive) > 1:
        await run_round(agents, round_num)
        round_num += 1

        alive = [a for a in agents if a.alive]
        if len(alive) == 1:
            break

        input("\n按 Enter 开始下一轮……")

    champion = next(a for a in agents if a.alive)
    print(f"\n{SEP}")
    print(f"  【最终胜者】{champion.name} 荣登大统！")
    print(SEP)
