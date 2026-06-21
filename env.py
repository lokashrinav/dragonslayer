"""Minecraft Speedrun RL Environment — HUD Hackathon (Gaming & Worldsims)"""

import asyncio
import json
import subprocess
import time
import os
import signal

import requests
from fastmcp import FastMCP
from hud.environment import Environment
from hud.capabilities import Capability

env = Environment(name="mc-speedrun")

BOT_API = "http://127.0.0.1:3001"
MC_SERVER_DIR = os.path.join(os.path.dirname(__file__), "server")

# Global process handles
_mc_server_proc = None
_bot_proc = None

# ============================================================================
# MCP TOOLS — actions the agent can take in Minecraft
# ============================================================================

mcp = FastMCP(name="minecraft-tools")


@mcp.tool()
async def look_around() -> str:
    """Observe surroundings: get position, health, food, inventory, nearby blocks and entities."""
    try:
        r = requests.get(f"{BOT_API}/state", timeout=10)
        state = r.json()
        lines = [
            f"Position: ({state['position']['x']:.1f}, {state['position']['y']:.1f}, {state['position']['z']:.1f})",
            f"Health: {state['health']}/20 | Food: {state['food']}/20",
            f"Dimension: {state['dimension']}",
            f"Time elapsed: {state['elapsed_seconds']:.0f}s",
            f"Inventory: {json.dumps(state['inventory']) if state['inventory'] else 'Empty'}",
            f"Nearby blocks: {json.dumps(state['nearby_blocks'])}",
            f"Nearby entities: {json.dumps(state['nearby_entities']) if state['nearby_entities'] else 'None'}",
            f"Objectives completed: {state['objectives_completed']}",
            f"Total reward: {state['total_reward']}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error observing: {e}"


@mcp.tool()
async def mine(block_name: str, count: int = 1) -> str:
    """Find and mine a specific block type. Examples: log (any wood), oak_log, cobblestone, iron_ore, diamond_ore, coal_ore, deepslate_iron_ore, deepslate_diamond_ore."""
    LOG_TYPES = ["oak_log", "birch_log", "spruce_log", "jungle_log", "dark_oak_log", "acacia_log"]

    BLOCK_ALIASES = {
        "cobblestone": "stone",
        "raw_iron": "iron_ore",
        "raw_gold": "gold_ore",
        "raw_copper": "copper_ore",
    }

    if block_name == "log":
        try:
            state_r = requests.get(f"{BOT_API}/state", timeout=5)
            nearby = state_r.json().get("nearby_blocks", {})
            present = [t for t in LOG_TYPES if t in nearby]
            absent = [t for t in LOG_TYPES if t not in nearby]
            names_to_try = present + absent
        except Exception:
            names_to_try = LOG_TYPES
    elif block_name in BLOCK_ALIASES:
        names_to_try = [BLOCK_ALIASES[block_name]]
    else:
        names_to_try = [block_name]

    last_error = None
    for name in names_to_try:
        try:
            r = requests.post(f"{BOT_API}/action", json={"action": "mine", "args": [name, count]}, timeout=120)
            data = r.json()
            result = data.get("result", {})
            state = data.get("state", {})
            if result.get("success") and result.get("mined", 0) > 0:
                completed = state.get("newly_completed", [])
                resp = f"Mine result: success, mined {result.get('mined', 0)} {name}"
                if completed:
                    resp += f"\n*** OBJECTIVES COMPLETED: {[o['name'] for o in completed]} ***"
                resp += f"\nInventory: {json.dumps(state.get('inventory', []))}"
                return resp
            last_error = result.get("error", "unknown")
        except Exception as e:
            last_error = str(e)

    return f"Mine result: failed to mine {block_name} (last error: {last_error})"


@mcp.tool()
async def craft(item_name: str, count: int = 1) -> str:
    """Craft an item. Use 'planks' to auto-detect wood type. Needs crafting table placed nearby for complex recipes. Examples: planks, stick, crafting_table, wooden_pickaxe, stone_pickaxe, furnace, iron_pickaxe."""
    PLANK_TYPES = ["oak_planks", "birch_planks", "spruce_planks", "jungle_planks", "dark_oak_planks", "acacia_planks"]

    names_to_try = PLANK_TYPES if item_name == "planks" else [item_name]

    for name in names_to_try:
        try:
            r = requests.post(f"{BOT_API}/action", json={"action": "craft", "args": [name, count]}, timeout=30)
            data = r.json()
            result = data.get("result", {})
            state = data.get("state", {})
            if result.get("success"):
                completed = state.get("newly_completed", [])
                resp = f"Craft result: success — crafted {count} {name}"
                if completed:
                    resp += f"\n*** OBJECTIVES COMPLETED: {[o['name'] for o in completed]} ***"
                resp += f"\nInventory: {json.dumps(state.get('inventory', []))}"
                return resp
        except Exception:
            continue

    return f"Craft result: failed to craft {item_name} (no matching recipe or missing materials)"


@mcp.tool()
async def place(block_name: str) -> str:
    """Place a block from inventory. Example: crafting_table, furnace."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "place", "args": [block_name]}, timeout=30)
        data = r.json()
        result = data.get("result", {})
        resp = f"Place result: {'success' if result.get('success') else 'failed'}"
        if result.get("error"):
            resp += f" ({result['error']})"
        return resp
    except Exception as e:
        return f"Error placing: {e}"


@mcp.tool()
async def smelt(item_name: str, fuel_name: str = "coal", count: int = 1) -> str:
    """Smelt items in a nearby furnace. Example: smelt('raw_iron', 'coal', 3). Furnace must be placed nearby."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "smelt", "args": [item_name, fuel_name, count]}, timeout=120)
        data = r.json()
        result = data.get("result", {})
        state = data.get("state", {})
        completed = state.get("newly_completed", [])
        resp = f"Smelt result: {'success' if result.get('success') else 'failed'}"
        if result.get("error"):
            resp += f" ({result['error']})"
        if completed:
            resp += f"\n*** OBJECTIVES COMPLETED: {[o['name'] for o in completed]} ***"
        resp += f"\nInventory: {json.dumps(state.get('inventory', []))}"
        return resp
    except Exception as e:
        return f"Error smelting: {e}"


@mcp.tool()
async def goto(x: float, y: float, z: float) -> str:
    """Navigate to specific coordinates."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "goto", "args": [x, y, z]}, timeout=60)
        data = r.json()
        result = data.get("result", {})
        resp = f"Goto result: {'arrived' if result.get('success') else 'failed'}"
        if result.get("error"):
            resp += f" ({result['error']})"
        if result.get("position"):
            p = result["position"]
            resp += f"\nNow at: ({p['x']:.1f}, {p['y']:.1f}, {p['z']:.1f})"
        return resp
    except Exception as e:
        return f"Error navigating: {e}"


@mcp.tool()
async def attack(entity_name: str) -> str:
    """Attack a nearby entity. Example: zombie, skeleton, creeper, enderman, blaze, pig, cow."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "attack", "args": [entity_name]}, timeout=30)
        data = r.json()
        result = data.get("result", {})
        resp = f"Attack result: {'success' if result.get('success') else 'failed'}"
        if result.get("error"):
            resp += f" ({result['error']})"
        return resp
    except Exception as e:
        return f"Error attacking: {e}"


@mcp.tool()
async def equip(item_name: str) -> str:
    """Equip an item from inventory. Example: wooden_pickaxe, stone_pickaxe, iron_sword."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "equip", "args": [item_name]}, timeout=10)
        data = r.json()
        result = data.get("result", {})
        resp = f"Equip result: {'success' if result.get('success') else 'failed'}"
        if result.get("error"):
            resp += f" ({result['error']})"
        return resp
    except Exception as e:
        return f"Error equipping: {e}"


@mcp.tool()
async def dig_to_y(target_y: int) -> str:
    """Dig down to a specific Y level. Use Y=-59 for diamonds, Y=11 for old diamond level."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "dig_to_y", "args": [target_y]}, timeout=300)
        data = r.json()
        result = data.get("result", {})
        state = data.get("state", {})
        completed = state.get("newly_completed", [])
        resp = f"Dug {result.get('dug', 0)} blocks, now at Y={result.get('y', '?')}"
        if completed:
            resp += f"\n*** OBJECTIVES COMPLETED: {[o['name'] for o in completed]} ***"
        resp += f"\nInventory: {json.dumps(state.get('inventory', []))}"
        return resp
    except Exception as e:
        return f"Error digging: {e}"


@mcp.tool()
async def build_nether_portal() -> str:
    """Build and light a nether portal near current position."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "build_nether_portal"}, timeout=30)
        data = r.json()
        result = data.get("result", {})
        if result.get("success"):
            return f"Nether portal built at {result.get('portal_pos')}. Walk into it to enter the nether."
        return f"Failed to build portal: {result.get('error')}"
    except Exception as e:
        return f"Error building portal: {e}"


@mcp.tool()
async def enter_portal() -> str:
    """Walk into a nearby nether/end portal to change dimension."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "enter_portal"}, timeout=30)
        data = r.json()
        result = data.get("result", {})
        state = data.get("state", {})
        completed = state.get("newly_completed", [])
        resp = f"Portal result: now in {result.get('dimension', 'unknown')}"
        if completed:
            resp += f"\n*** OBJECTIVES COMPLETED: {[o['name'] for o in completed]} ***"
        return resp
    except Exception as e:
        return f"Error entering portal: {e}"


@mcp.tool()
async def find_structure(structure_name: str) -> str:
    """Find the nearest structure. Examples: fortress, stronghold, village, bastion_remnant, end_city."""
    try:
        r = requests.post(f"{BOT_API}/action", json={"action": "find_structure", "args": [structure_name]}, timeout=15)
        data = r.json()
        result = data.get("result", {})
        if result.get("success"):
            return f"Found {structure_name} at X={result['x']}, Z={result['z']}"
        return f"Could not find {structure_name}: {result.get('error')}"
    except Exception as e:
        return f"Error finding structure: {e}"


# ============================================================================
# SPEEDRUN OBJECTIVES — defines what we grade on
# ============================================================================

OBJECTIVES = {
    # Easy tier — ~60-90% success rate expected
    "get_wood": {"name": "Get Wood", "reward_weight": 10, "time_limit": 120},
    "craft_planks": {"name": "Craft Planks", "reward_weight": 5, "time_limit": 180},
    "craft_crafting_table": {"name": "Craft Crafting Table", "reward_weight": 15, "time_limit": 240},
    "craft_wooden_pickaxe": {"name": "Craft Wooden Pickaxe", "reward_weight": 15, "time_limit": 300},

    # Medium tier — ~20-50% success rate expected
    "get_cobblestone": {"name": "Mine Cobblestone", "reward_weight": 10, "time_limit": 360},
    "craft_stone_pickaxe": {"name": "Craft Stone Pickaxe", "reward_weight": 20, "time_limit": 420},
    "get_iron_ore": {"name": "Mine Iron Ore", "reward_weight": 25, "time_limit": 600},
    "craft_furnace": {"name": "Craft Furnace", "reward_weight": 15, "time_limit": 600},
    "smelt_iron": {"name": "Smelt Iron Ingots", "reward_weight": 30, "time_limit": 900},
    "craft_iron_pickaxe": {"name": "Craft Iron Pickaxe", "reward_weight": 30, "time_limit": 900},

    # Hard tier — ~5-15% success rate expected
    "get_diamonds": {"name": "Mine Diamonds", "reward_weight": 50, "time_limit": 1200},
    "craft_diamond_pickaxe": {"name": "Craft Diamond Pickaxe", "reward_weight": 50, "time_limit": 1200},
    "enter_nether": {"name": "Enter Nether", "reward_weight": 100, "time_limit": 1800},
    "get_blaze_rods": {"name": "Get Blaze Rods", "reward_weight": 75, "time_limit": 2400},
}

# Real speedrun reference times (world record ~8 min, good run ~15 min, casual ~45 min)
SPEEDRUN_REFERENCE = {
    "get_wood": 15,           # seconds — punch a tree
    "craft_wooden_pickaxe": 45,  # seconds — basic tool chain
    "craft_stone_pickaxe": 90,   # seconds — mine stone, craft
    "craft_iron_pickaxe": 300,   # 5 min — find iron, smelt
    "get_diamonds": 480,         # 8 min — mine deep, find diamonds
    "enter_nether": 600,         # 10 min — build portal
}


def compute_reward(objective_id: str, completed: bool, elapsed_seconds: float) -> float:
    """Compute reward for a task. 0.0-1.0 scale.

    - 0.0 if objective not completed
    - 0.5 if completed (base)
    - Up to 1.0 if completed fast (bonus based on reference speedrun times)
    """
    if not completed:
        return 0.0

    obj = OBJECTIVES[objective_id]
    base_reward = 0.5

    ref_time = SPEEDRUN_REFERENCE.get(objective_id, obj["time_limit"] * 0.5)
    time_limit = obj["time_limit"]

    if elapsed_seconds <= ref_time:
        time_bonus = 0.5  # max bonus for beating reference
    elif elapsed_seconds >= time_limit:
        time_bonus = 0.0  # no bonus, just barely made it
    else:
        time_bonus = 0.5 * (1.0 - (elapsed_seconds - ref_time) / (time_limit - ref_time))

    return min(1.0, base_reward + time_bonus)


# ============================================================================
# TASK TEMPLATES — what agents get evaluated on
# ============================================================================

@env.template(id="speedrun_easy")
async def speedrun_easy(objective: str = "craft_wooden_pickaxe"):
    """Easy speedrun task: achieve a basic objective (wood, planks, crafting table, wooden pickaxe)."""
    obj = OBJECTIVES.get(objective, OBJECTIVES["craft_wooden_pickaxe"])
    time_limit = obj["time_limit"]

    answer = yield (
        f"You are a Minecraft speedrun agent. Your goal: {obj['name']}.\n"
        f"Time limit: {time_limit} seconds.\n\n"
        f"You have tools to interact with Minecraft: look_around, mine, craft, place, smelt, goto, attack, equip.\n"
        f"Start by calling look_around to observe your surroundings, then work toward the objective.\n\n"
        f"SPEEDRUN STRATEGY for wooden pickaxe:\n"
        f"1. mine('log', 3) — punch trees\n"
        f"2. craft('planks', 3) — make planks\n"
        f"3. craft('crafting_table', 1) — make crafting table\n"
        f"4. place('crafting_table') — place it\n"
        f"5. craft('stick', 1) — make sticks\n"
        f"6. craft('wooden_pickaxe', 1) — make the pickaxe\n\n"
        f"Call tools to complete the objective. When done, respond with 'DONE'."
    )

    # Check if objective was achieved
    try:
        r = requests.get(f"{BOT_API}/state", timeout=10)
        state = r.json()
        completed = objective in state.get("objectives_completed", [])
        elapsed = state.get("elapsed_seconds", 9999)
        reward = compute_reward(objective, completed, elapsed)
        yield reward
    except Exception:
        yield 0.0


@env.template(id="speedrun_medium")
async def speedrun_medium(objective: str = "craft_iron_pickaxe"):
    """Medium speedrun task: get iron tools. Requires mining, smelting, multi-step crafting."""
    obj = OBJECTIVES.get(objective, OBJECTIVES["craft_iron_pickaxe"])
    time_limit = obj["time_limit"]

    answer = yield (
        f"You are a Minecraft speedrun agent. Your goal: {obj['name']}.\n"
        f"Time limit: {time_limit} seconds.\n\n"
        f"You have tools: look_around, mine, craft, place, smelt, goto, attack, equip.\n"
        f"Start by calling look_around.\n\n"
        f"SPEEDRUN STRATEGY for iron pickaxe:\n"
        f"1. mine('log', 5) — get wood\n"
        f"2. craft('planks', 5) — make planks\n"
        f"3. craft('crafting_table', 1) + place('crafting_table')\n"
        f"4. craft('stick', 2) — make sticks\n"
        f"5. craft('wooden_pickaxe', 1) — make first pickaxe\n"
        f"6. mine('cobblestone', 8) — mine stone\n"
        f"7. craft('stone_pickaxe', 1) — upgrade pickaxe\n"
        f"8. craft('furnace', 1) + place('furnace')\n"
        f"9. mine('iron_ore', 3) + mine('coal_ore', 3)\n"
        f"10. smelt('raw_iron', 'coal', 3) — smelt iron\n"
        f"11. craft('iron_pickaxe', 1) — craft iron pickaxe\n\n"
        f"Call tools to complete the objective. When done, respond with 'DONE'."
    )

    try:
        r = requests.get(f"{BOT_API}/state", timeout=10)
        state = r.json()
        completed = objective in state.get("objectives_completed", [])
        elapsed = state.get("elapsed_seconds", 9999)
        reward = compute_reward(objective, completed, elapsed)
        yield reward
    except Exception:
        yield 0.0


@env.template(id="speedrun_hard")
async def speedrun_hard(objective: str = "get_diamonds"):
    """Hard speedrun task: get diamonds or enter the nether. Requires deep mining or portal building."""
    obj = OBJECTIVES.get(objective, OBJECTIVES["get_diamonds"])
    time_limit = obj["time_limit"]

    answer = yield (
        f"You are a Minecraft speedrun agent. Your goal: {obj['name']}.\n"
        f"Time limit: {time_limit} seconds.\n\n"
        f"You have tools: look_around, mine, craft, place, smelt, goto, attack, equip.\n"
        f"Start by calling look_around.\n\n"
        f"STRATEGY:\n"
        f"- Get iron tools first (follow medium strategy)\n"
        f"- For diamonds: dig down to Y=-59, mine at diamond level\n"
        f"- For nether: find/create lava+water for obsidian, build portal, light with flint_and_steel\n\n"
        f"Call tools to complete the objective. When done, respond with 'DONE'."
    )

    try:
        r = requests.get(f"{BOT_API}/state", timeout=10)
        state = r.json()
        completed = objective in state.get("objectives_completed", [])
        elapsed = state.get("elapsed_seconds", 9999)
        reward = compute_reward(objective, completed, elapsed)
        yield reward
    except Exception:
        yield 0.0


@env.template(id="speedrun_full")
async def speedrun_full():
    """Full speedrun: achieve as many objectives as possible. Graded on cumulative progress."""
    answer = yield (
        "You are a Minecraft speedrun agent. Complete as many objectives as possible, as fast as possible.\n\n"
        "Objectives (in order):\n"
        "1. Get Wood\n"
        "2. Craft Planks\n"
        "3. Craft Crafting Table\n"
        "4. Craft Wooden Pickaxe\n"
        "5. Mine Cobblestone\n"
        "6. Craft Stone Pickaxe\n"
        "7. Mine Iron Ore\n"
        "8. Craft Furnace\n"
        "9. Smelt Iron Ingots\n"
        "10. Craft Iron Pickaxe\n"
        "11. Mine Diamonds\n"
        "12. Craft Diamond Pickaxe\n"
        "13. Enter Nether\n"
        "14. Get Blaze Rods\n\n"
        "You have tools: look_around, mine, craft, place, smelt, goto, attack, equip.\n"
        "Start by calling look_around, then speedrun through the objectives.\n"
        "When done or stuck, respond with 'DONE'."
    )

    try:
        r = requests.get(f"{BOT_API}/state", timeout=10)
        state = r.json()
        completed = state.get("objectives_completed", [])
        total_possible = sum(obj["reward_weight"] for obj in OBJECTIVES.values())
        total_earned = sum(
            OBJECTIVES[oid]["reward_weight"]
            for oid in completed
            if oid in OBJECTIVES
        )
        yield total_earned / total_possible if total_possible > 0 else 0.0
    except Exception:
        yield 0.0


# ============================================================================
# LIFECYCLE — start Minecraft server + bot on env init
# ============================================================================

@env.initialize
async def _start():
    global _mc_server_proc, _bot_proc

    # Start Minecraft server
    server_dir = MC_SERVER_DIR
    if os.path.exists(os.path.join(server_dir, "server.jar")):
        _mc_server_proc = subprocess.Popen(
            ["java", "-Xmx2G", "-Xms1G", "-jar", "server.jar", "nogui"],
            cwd=server_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        # Wait for server to be ready
        for _ in range(120):
            await asyncio.sleep(1)
            if _mc_server_proc.stdout:
                line = _mc_server_proc.stdout.readline().decode(errors="replace")
                if "Done" in line:
                    break

    # Start Mineflayer bot
    bot_path = os.path.join(os.path.dirname(__file__), "bot.js")
    if os.path.exists(bot_path):
        _bot_proc = subprocess.Popen(
            ["node", bot_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        await asyncio.sleep(5)  # let bot connect and spawn

    # Reset timer
    try:
        requests.post(f"{BOT_API}/reset", timeout=5)
    except Exception:
        pass

    # Register MCP tools
    asyncio.create_task(mcp.run_http_async(host="127.0.0.1", port=8766))
    await asyncio.sleep(0.5)
    env.add_capability(Capability.mcp(name="minecraft", url="http://127.0.0.1:8766/mcp"))


@env.shutdown
async def _stop():
    global _mc_server_proc, _bot_proc
    if _bot_proc:
        _bot_proc.terminate()
        _bot_proc = None
    if _mc_server_proc:
        _mc_server_proc.terminate()
        _mc_server_proc = None


# ============================================================================
# LOCAL TEST
# ============================================================================

async def test():
    from hud.agents.claude import ClaudeAgent
    from hud import LocalRuntime

    agent = ClaudeAgent()
    task = speedrun_easy(objective="get_wood")
    job = await task.run(agent, runtime=LocalRuntime(__file__))
    print(f"Reward: {job.reward}")


if __name__ == "__main__":
    asyncio.run(test())
