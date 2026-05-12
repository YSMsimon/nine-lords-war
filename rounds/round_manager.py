import asyncio
import contextlib
import json
import random
from typing import Callable

from agents.base_agent import Agent, _client
from core.bridge import GameBridge

SPEAK_COOLDOWN = 10
MAX_DISCUSSION_ROUNDS = 2
MAX_RETRIES = 3

PRESET_QUESTIONS = [
    "国库亏空，仅剩三百万两白银，如何在一年内充实国库？",
    "北疆异族大举入侵，边境十城告急，如何以最小代价平定战局？",
    "江南连年水患，百万流民涌入京城，民怨沸腾，如何安置？",
    "科举舞弊案震惊朝野，寒门学子聚集午门请愿，如何处置？",
    "皇上有意削藩，如何在不引发内乱的前提下推进？",
    "西洋传教士带来奇技淫巧，是闭关锁国还是开放通商？",
    "太后病危，朝中两派争夺监国之权，如何稳定局势？",
]


# ── Tool schemas ──────────────────────────────────────────────────────────────

def _discussion_tools(agent: Agent) -> list[dict]:
    from tools.declare_alliance_tool import DeclareAllianceTool
    from tools.alliance_decision_tool import AllianceDecisionTool
    from tools.private_message_tool import PrivateMessageTool
    schemas: list[dict] = []
    for cls in (DeclareAllianceTool, AllianceDecisionTool, PrivateMessageTool):
        schemas.extend(cls(agent).get_schema())
    return schemas


def _vote_schema(agent: Agent) -> list[dict]:
    from tools.vote_tool import VoteTool
    return VoteTool(agent).get_schema()


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _retrying_tool_call(
    agent: Agent,
    schemas: list[dict],
    tool_choice: dict | str,
    validate: Callable[[str, dict], None],
) -> tuple[str, str, dict] | None:
    """
    Call the model with tools, retrying up to MAX_RETRIES times.
    On parse or validation error the error is fed back into messages so the model
    can correct itself.  Returns (fn_name, tool_call_id, args) or None if exhausted.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = await _client.chat.completions.create(
                model=agent.model,
                messages=agent.messages,
                tools=schemas,
                tool_choice=tool_choice,
            )
        except Exception as e:
            # Network / API error — treat as retry-able
            if attempt < MAX_RETRIES - 1:
                agent.messages.append({
                    "role": "user",
                    "content": f"[系统] API 调用失败：{e}，正在重试（第 {attempt+2}/{MAX_RETRIES} 次）",
                })
            continue

        msg = resp.choices[0].message

        if not msg.tool_calls:
            agent.messages.append({"role": "assistant", "content": msg.content or ""})
            if attempt < MAX_RETRIES - 1:
                agent.messages.append({
                    "role": "user",
                    "content": (
                        f"[系统] 未检测到工具调用，请使用指定工具"
                        f"（第 {attempt+2}/{MAX_RETRIES} 次尝试）"
                    ),
                })
            continue

        tc = msg.tool_calls[0]
        assistant_entry: dict = {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [{
                "id": tc.id, "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }],
        }

        try:
            args = json.loads(tc.function.arguments)
            validate(tc.function.name, args)          # raises ValueError if bad
            agent.messages.append(assistant_entry)
            return tc.function.name, tc.id, args

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            err = str(e)
            agent.messages.append(assistant_entry)
            agent.messages.append({"role": "tool", "tool_call_id": tc.id,
                                   "content": f"[格式错误] {err}"})
            if attempt < MAX_RETRIES - 1:
                agent.messages.append({
                    "role": "user",
                    "content": (
                        f"[系统] 工具参数错误（{err}），请修正后重新调用"
                        f"（第 {attempt+2}/{MAX_RETRIES} 次尝试）"
                    ),
                })

    return None  # all retries exhausted


# ── Discussion tool handler ───────────────────────────────────────────────────

async def _handle_tool_call(
    agent: Agent, fn: str, args: dict,
    all_agents: list[Agent], shared_memory: list[str], bridge: GameBridge,
) -> str:
    if fn == "speak":
        return args.get("content", "")

    if fn == "declare_alliance":
        target, reason = args.get("target", ""), args.get("reason", "")
        notice = f"【结盟提议】{agent.name} → {target}：{reason}"
        shared_memory.append(notice)
        await bridge.broadcast({"type": "alliance_proposal",
                                "from": agent.name, "to": target, "reason": reason})
        return json.dumps({"proposer": agent.name, "target": target, "reason": reason},
                          ensure_ascii=False)

    if fn == "alliance_decision":
        partner = args.get("partner", "")
        action  = args.get("action", "reject")
        reason  = args.get("reason", "")
        label   = {"accept": "接受结盟", "reject": "拒绝结盟", "breakup": "解除同盟"}.get(action, action)
        notice  = f"【{label}】{agent.name} ↔ {partner}：{reason}"
        shared_memory.append(notice)
        await bridge.broadcast({"type": "alliance_decision", "agent": agent.name,
                                "partner": partner, "action": action, "reason": reason})
        return notice

    if fn == "private_message":
        target, message = args.get("target", ""), args.get("message", "")
        await bridge.broadcast({"type": "private_message",
                                "from": agent.name, "to": target, "message": message})
        # Store in both sender's and receiver's memory
        entry = f"私信（{agent.name} → {target}）：{message}"
        agent.memory.store(entry, meta={"type": "private_message",
                                        "direction": "sent", "to": target})
        receiver = next((a for a in all_agents if a.name == target), None)
        if receiver:
            receiver.memory.store(entry, meta={"type": "private_message",
                                               "direction": "received", "from": agent.name})
        return f"私信已送达 {target}"

    return "工具执行完毕"


def _validate_discussion(fn: str, args: dict) -> None:
    if fn == "declare_alliance":
        if not args.get("target") or not args.get("reason"):
            raise ValueError("declare_alliance 需要 target 和 reason")
    elif fn == "alliance_decision":
        if args.get("action") not in ("accept", "reject", "breakup"):
            raise ValueError("action 必须是 accept / reject / breakup 之一")
        if not args.get("partner"):
            raise ValueError("alliance_decision 需要 partner")
    elif fn == "private_message":
        if not args.get("target") or not args.get("message"):
            raise ValueError("private_message 需要 target 和 message")


async def _agent_discussion_turn(
    agent: Agent, prompt: str,
    all_agents: list[Agent], shared_memory: list[str], bridge: GameBridge,
) -> str:
    agent.messages.append({"role": "user", "content": prompt})
    last_error = ""

    for attempt in range(MAX_RETRIES):
        try:
            resp = await _client.chat.completions.create(
                model=agent.model,
                messages=agent.messages,
                tools=_discussion_tools(agent),
                tool_choice="auto",
            )
        except Exception as e:
            last_error = str(e)
            continue

        msg = resp.choices[0].message

        # Pure text — this is the speech
        if not msg.tool_calls:
            content = msg.content or f"（{agent.name} 返回空内容）"
            agent.messages.append({"role": "assistant", "content": content})
            return content

        tc = msg.tool_calls[0]
        assistant_entry: dict = {
            "role": "assistant", "content": msg.content,
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}],
        }

        try:
            args = json.loads(tc.function.arguments)
            _validate_discussion(tc.function.name, args)
            agent.messages.append(assistant_entry)

            # Execute tool, then get follow-up text as the spoken content
            tool_result = await _handle_tool_call(
                agent, tc.function.name, args, all_agents, shared_memory, bridge
            )
            agent.messages.append({"role": "tool", "tool_call_id": tc.id,
                                   "content": tool_result})

            try:
                follow = await _client.chat.completions.create(
                    model=agent.model, messages=agent.messages
                )
                content = follow.choices[0].message.content or f"（{agent.name} 工具后续响应为空）"
            except Exception as e:
                content = f"（{agent.name} 工具执行完毕，后续响应失败：{e}）"

            agent.messages.append({"role": "assistant", "content": content})
            return content

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            err = str(e)
            last_error = err
            agent.messages.append(assistant_entry)
            agent.messages.append({"role": "tool", "tool_call_id": tc.id,
                                   "content": f"[格式错误] {err}"})
            if attempt < MAX_RETRIES - 1:
                agent.messages.append({"role": "user",
                                       "content": f"[系统] 工具参数错误（{err}），请修正（第 {attempt+2} 次）"})

    # All retries exhausted — always return something visible
    fallback = f"（{agent.name} 发言失败：{last_error or '已达最大重试次数'}）"
    agent.messages.append({"role": "assistant", "content": fallback})
    return fallback


# ── Phase 1: Proposal ─────────────────────────────────────────────────────────

async def run_proposal_phase(
    alive: list[Agent], question: str,
    shared_memory: list[str], bridge: GameBridge, round_num: int,
) -> None:
    await bridge.broadcast({"type": "phase", "phase": "proposal", "round": round_num})

    async def propose(agent: Agent) -> None:
        # Pull relevant past memories
        past = agent.memory.query(question, n=4)
        memory_ctx = ("\n往期记忆：\n" + "\n".join(f"- {m}" for m in past)) if past else ""

        prompt = (
            f"皇上今日出题：{question}{memory_ctx}"
            f"{bridge.get_king_context()}\n\n"
            f"请提交你的施政方案。只输出你在朝堂上实际说的话，"
            f"不要描述动作、表情或场景（不要出现星号动作描写或第三人称叙述）。"
        )
        agent.messages.append({"role": "user", "content": prompt})
        try:
            resp = await _client.chat.completions.create(
                model=agent.model, messages=agent.messages
            )
            content = resp.choices[0].message.content or ""
        except Exception as e:
            content = f"（{agent.name} 未能提交方案：{e}）"



        agent.messages.append({"role": "assistant", "content": content})

        entry = f"【{agent.name}的方案】{content}"
        shared_memory.append(entry)
        agent.memory.store(entry, meta={"type": "proposal", "round": round_num,
                                        "question": question})
        await bridge.broadcast({"type": "speak", "agent": agent.name,
                                "content": content, "phase": "proposal"})

    await asyncio.gather(*[propose(a) for a in alive])


# ── Phase 2: Discussion ───────────────────────────────────────────────────────

async def _discussion_loop(
    alive: list[Agent], shared_memory: list[str],
    bridge: GameBridge, round_num: int,
) -> None:
    for _ in range(MAX_DISCUSSION_ROUNDS):
        order = [a for a in alive if a.alive]
        random.shuffle(order)

        for agent in order:
            if not agent.alive:
                continue

            history = "\n".join(shared_memory[-12:])
            past = agent.memory.query(history[:200], n=3)
            memory_ctx = ("\n往期记忆：\n" + "\n".join(f"- {m}" for m in past)) if past else ""

            prompt = (
                f"朝堂共享记录：\n{history}{memory_ctx}"
                f"{bridge.get_king_context()}\n\n"
                f"现在是发言阶段。直接说出你想说的话，可以使用工具结盟、私信或回应结盟请求。"
                f"只输出你在朝堂上实际说的话，不要描述动作、表情或场景，不要出现星号动作描写或第三人称叙述。"
            )
            content = await _agent_discussion_turn(
                agent, prompt, alive, shared_memory, bridge
            )
            entry = f"【{agent.name}】{content}"
            shared_memory.append(entry)
            agent.memory.store(entry, meta={"type": "discussion", "round": round_num})
            await bridge.broadcast({"type": "speak", "agent": agent.name,
                                        "content": content, "phase": "discussion"})

            await asyncio.sleep(SPEAK_COOLDOWN)


async def run_discussion_phase(
    alive: list[Agent], shared_memory: list[str],
    bridge: GameBridge, round_num: int,
) -> None:
    await bridge.broadcast({"type": "phase", "phase": "discussion", "round": round_num})
    bridge.king_proceed.clear()

    loop_task    = asyncio.create_task(_discussion_loop(alive, shared_memory, bridge, round_num))
    proceed_task = asyncio.create_task(bridge.king_proceed.wait())

    done, pending = await asyncio.wait(
        [loop_task, proceed_task], return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t


# ── Phase 3: Vote ─────────────────────────────────────────────────────────────

async def run_vote_phase(
    alive: list[Agent], shared_memory: list[str],
    bridge: GameBridge, round_num: int,
) -> str:
    await bridge.broadcast({"type": "phase", "phase": "vote", "round": round_num})

    alive_names = [a.name for a in alive if a.alive]
    history = "\n".join(shared_memory[-15:])

    async def vote(agent: Agent) -> tuple[str, str]:
        others = [n for n in alive_names if n != agent.name]

        def validate_vote(fn: str, args: dict) -> None:
            if fn != "vote":
                raise ValueError(f"投票阶段只能使用 vote 工具，收到 {fn}")
            target = args.get("target", "")
            if target not in others:
                raise ValueError(
                    f"'{target}' 不在候选人列表中，请从以下选择：{', '.join(others)}"
                )

        prompt = (
            f"朝堂完整记录：\n{history}\n\n"
            f"现在是投票阶段，只能使用 vote 工具。"
            f"你必须投票淘汰一人，不能投自己。候选人：{', '.join(others)}"
        )
        agent.messages.append({"role": "user", "content": prompt})

        result = await _retrying_tool_call(
            agent,
            schemas=_vote_schema(agent),
            tool_choice={"type": "function", "function": {"name": "vote"}},
            validate=validate_vote,
        )

        if result:
            fn, tc_id, args = result
            target = args["target"]
            agent.messages.append({"role": "tool", "tool_call_id": tc_id,
                                   "content": f"投票成功：{target}"})
            agent.memory.store(f"第{round_num}轮投票淘汰：{target}",
                               meta={"type": "vote", "round": round_num, "target": target})
            return agent.name, target
        else:
            # All retries exhausted — random fallback
            fallback = random.choice(others)
            agent.memory.store(f"第{round_num}轮投票（放弃/随机）：{fallback}",
                               meta={"type": "vote_fallback", "round": round_num})
            return agent.name, fallback

    results = await asyncio.gather(*[vote(a) for a in alive if a.alive])
    vote_map = dict(results)

    tally: dict[str, int] = {n: 0 for n in alive_names}
    for target in vote_map.values():
        if target in tally:
            tally[target] += 1

    await bridge.broadcast({"type": "votes", "votes": vote_map, "tally": tally})

    max_votes = max(tally.values(), default=0)
    leaders = [n for n, v in tally.items() if v == max_votes]
    if len(leaders) > 1:
        await bridge.broadcast({"type": "tie", "agents": leaders, "votes": max_votes})
        return None
    return leaders[0]


# ── Elimination ───────────────────────────────────────────────────────────────

async def run_elimination(
    eliminated: str, agents: list[Agent], bridge: GameBridge, round_num: int,
) -> None:
    await bridge.broadcast({
        "type": "elimination_pending",
        "target": eliminated,
    })
    bridge.drain_queue()

    saved = False

    while True:
        cmd = await bridge.next_command(timeout=None)
        if cmd is None:
            continue
        t = cmd.get("type")
        if t == "king_save" and cmd.get("target") == eliminated:
            await bridge.broadcast({"type": "king_action", "action": "save", "target": eliminated})
            await bridge.broadcast({"type": "saved", "target": eliminated})
            saved = True
            break
        if t == "king_confirm_elimination":
            break

    if not saved:
        for a in agents:
            if a.name == eliminated:
                a.alive = False
                a.memory.store(f"第{round_num}轮被淘汰出局",
                               meta={"type": "eliminated", "round": round_num})
        await bridge.broadcast({"type": "eliminated", "target": eliminated})
    else:
        for a in agents:
            if a.name == eliminated:
                a.memory.store(f"第{round_num}轮遭投票淘汰但获皇上赦免",
                               meta={"type": "saved", "round": round_num})


# ── Round orchestrator ────────────────────────────────────────────────────────

async def wait_for_king_question(bridge: GameBridge) -> str:
    bridge.accepting_question = True
    await bridge.broadcast({"type": "waiting_question", "presets": PRESET_QUESTIONS})
    while True:
        cmd = await bridge.next_command(timeout=None)
        if cmd and cmd.get("type") == "king_question":
            bridge.accepting_question = False
            return cmd["content"]


async def run_round(agents: list[Agent], round_num: int, bridge: GameBridge) -> bool:
    alive = [a for a in agents if a.alive]
    shared_memory: list[str] = []

    await bridge.broadcast({
        "type": "round_start", "round": round_num,
        "alive": [a.name for a in alive],
    })

    # 1. King chooses question
    question = await wait_for_king_question(bridge)
    await bridge.broadcast({"type": "question", "content": question})

    # 2. Proposal phase — no tools, async gather
    await run_proposal_phase(alive, question, shared_memory, bridge, round_num)

    # 3. King manually proceeds to discussion
    if not await bridge.wait_for_king_proceed("proposal_done"):
        return False

    # 4. Discussion phase — all tools except vote
    alive = [a for a in agents if a.alive]
    await run_discussion_phase(alive, shared_memory, bridge, round_num)

    # 5. King manually proceeds to vote
    if not await bridge.wait_for_king_proceed("discussion_done"):
        return False

    # 6. Vote phase — vote tool only, with retry
    alive = [a for a in agents if a.alive]
    eliminated = await run_vote_phase(alive, shared_memory, bridge, round_num)

    # 7. King saves or confirms (skip on tie)
    if eliminated:
        await run_elimination(eliminated, agents, bridge, round_num)

    # 8. King manually continues or ends game
    return await bridge.wait_for_king_proceed("round_done")


async def _king_respond(agent: Agent, king_message: str, bridge: GameBridge, phase: str) -> None:
    past = agent.memory.query(king_message, n=4)
    memory_ctx = ("\n往期记忆：\n" + "\n".join(f"- {m}" for m in past)) if past else ""
    history_ctx = bridge.get_king_context()

    if phase == "king_at":
        instruction = f"皇上单独垂询你：{king_message}"
    else:
        instruction = f"皇上降旨，命诸皇子各抒己见：{king_message}"

    messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "user", "content": (
            f"{history_ctx}\n\n{instruction}{memory_ctx}\n\n"
            f"只输出你实际说的话，不要描述动作或场景。"
        )},
    ]
    try:
        resp = await _client.chat.completions.create(model=agent.model, messages=messages)
        text = resp.choices[0].message.content or f"（{agent.name} 沉默不语）"
    except Exception as e:
        text = f"（{agent.name} 无法回应：{e}）"

    label = "单独垂询" if phase == "king_at" else "皇上降旨"
    agent.memory.store(f"{label}「{king_message}」，臣回应：{text}", meta={"type": phase})
    await bridge.broadcast({"type": "speak", "agent": agent.name, "content": text, "phase": phase})


async def king_address_all(content: str, bridge: GameBridge) -> None:
    alive = [a for a in bridge.agents if a.alive]
    await asyncio.gather(*[_king_respond(a, content, bridge, "king_address") for a in alive])


async def king_at_agent(target_name: str, content: str, bridge: GameBridge) -> None:
    agent = next((a for a in bridge.agents if a.name == target_name and a.alive), None)
    if agent:
        await _king_respond(agent, content, bridge, "king_at")


async def run_game(agents: list[Agent], bridge: GameBridge) -> None:
    await bridge.broadcast({"type": "game_start", "agents": [a.name for a in agents]})

    round_num = 1
    while sum(1 for a in agents if a.alive) > 1:
        if not await run_round(agents, round_num, bridge):
            break
        round_num += 1

    alive = [a for a in agents if a.alive]
    if alive:
        await bridge.broadcast({"type": "game_over", "champion": alive[0].name})
