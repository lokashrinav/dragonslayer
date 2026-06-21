"""Claude agent that plays Minecraft speedrun via MCP tools."""
import json
import time
import os
import requests
import anthropic

BOT_API = "http://127.0.0.1:3001"

with open(os.path.expanduser("~/.env")) as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

client = anthropic.Anthropic()

TOOLS = [
    {"name": "look_around", "description": "Get position, health, inventory, nearby blocks/entities, objectives.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "mine", "description": "Find+mine a block. 'stone'->cobblestone, 'iron_ore'->raw_iron, 'coal_ore'->coal, 'diamond_ore'->diamond. For wood specify type: oak_log, dark_oak_log, birch_log, spruce_log.", "input_schema": {"type": "object", "properties": {"block_name": {"type": "string"}, "count": {"type": "integer", "default": 1}}, "required": ["block_name"]}},
    {"name": "craft", "description": "Craft item. Recipes: [type]_planks(1 log->4), stick(2 planks->4), crafting_table(4 planks), wooden/stone/iron/diamond_pickaxe, wooden/stone/iron/diamond_sword, furnace(8 cobblestone), bucket(3 iron_ingot), torch(stick+coal), iron armor, shield, flint_and_steel, blaze_powder(blaze_rod->2), ender_eye(ender_pearl+blaze_powder).", "input_schema": {"type": "object", "properties": {"item_name": {"type": "string"}, "count": {"type": "integer", "default": 1}}, "required": ["item_name"]}},
    {"name": "smelt", "description": "Smelt items. raw_iron->iron_ingot, raw_gold->gold_ingot. Needs fuel.", "input_schema": {"type": "object", "properties": {"item_name": {"type": "string"}, "fuel": {"type": "string", "default": "coal"}, "count": {"type": "integer", "default": 1}}, "required": ["item_name"]}},
    {"name": "place", "description": "Place block from inventory.", "input_schema": {"type": "object", "properties": {"block_name": {"type": "string"}}, "required": ["block_name"]}},
    {"name": "goto", "description": "Navigate to coordinates.", "input_schema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}, "required": ["x", "y", "z"]}},
    {"name": "attack", "description": "Attack nearby entity til dead. Works for zombies, skeletons, blazes, endermen, etc.", "input_schema": {"type": "object", "properties": {"entity_name": {"type": "string"}}, "required": ["entity_name"]}},
    {"name": "equip", "description": "Equip item to hand.", "input_schema": {"type": "object", "properties": {"item_name": {"type": "string"}}, "required": ["item_name"]}},
    {"name": "dig_to_y", "description": "Dig down to Y level. Y=-59 for diamonds. Collects drops.", "input_schema": {"type": "object", "properties": {"target_y": {"type": "integer"}}, "required": ["target_y"]}},
    {"name": "build_nether_portal", "description": "Build+light nether portal near you. No materials needed.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "enter_portal", "description": "Step into nearby portal to change dimension.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "find_structure", "description": "Locate nearest structure: fortress, stronghold, village, bastion_remnant.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
]

def execute_tool(name, inp):
    if name == "look_around":
        return json.dumps(requests.get(f"{BOT_API}/state", timeout=10).json(), indent=2)

    arg_map = {
        "mine": lambda i: ("mine", [i["block_name"], i.get("count", 1)]),
        "craft": lambda i: ("craft", [i["item_name"], i.get("count", 1)]),
        "smelt": lambda i: ("smelt", [i["item_name"], i.get("fuel", "coal"), i.get("count", 1)]),
        "place": lambda i: ("place", [i["block_name"]]),
        "goto": lambda i: ("goto", [i["x"], i["y"], i["z"]]),
        "attack": lambda i: ("attack", [i["entity_name"]]),
        "equip": lambda i: ("equip", [i["item_name"]]),
        "dig_to_y": lambda i: ("dig_to_y", [i["target_y"]]),
        "build_nether_portal": lambda i: ("build_nether_portal", []),
        "enter_portal": lambda i: ("enter_portal", []),
        "find_structure": lambda i: ("find_structure", [i["name"]]),
    }
    action, args = arg_map[name](inp)
    r = requests.post(f"{BOT_API}/action", json={"action": action, "args": args}, timeout=300)
    data = r.json()
    return json.dumps({"result": data.get("result", {}), "position": data.get("state", {}).get("position"), "health": data.get("state", {}).get("health"), "inventory": data.get("state", {}).get("inventory"), "objectives_completed": data.get("state", {}).get("objectives_completed"), "newly_completed": data.get("state", {}).get("newly_completed"), "nearby_entities": (data.get("state", {}).get("nearby_entities") or [])[:5]}, indent=2)

SYSTEM = """You are a Minecraft speedrun agent. YOUR GOAL: KILL THE ENDER DRAGON. Every decision should move toward that goal.

FULL SPEEDRUN PATH (follow this order):
PHASE 1 — OVERWORLD TOOLS:
1. look_around. Mine the log type nearby (oak_log, birch_log, dark_oak_log, etc.)
2. Mine 5 logs → craft planks(5), stick(2), crafting_table, wooden_pickaxe
3. Mine 11 stone → craft stone_pickaxe + furnace
4. Mine 3 iron_ore + 3 coal_ore → smelt('raw_iron','coal',3) → craft iron_pickaxe
5. Craft iron_sword (2 iron_ingot + 1 stick) — you NEED a weapon for blazes/endermen/dragon

PHASE 2 — NETHER (after iron tools):
6. build_nether_portal → enter_portal (portal is FREE, costs nothing)
7. find_structure("fortress") to locate a nether fortress
8. Go to fortress, attack("blaze") repeatedly until you have 7+ blaze_rods
9. craft blaze_powder from blaze_rods

PHASE 3 — ENDER PEARLS (back in overworld or nether):
10. Hunt endermen: attack("enderman") — need 12 ender_pearls
11. craft ender_eye (needs 1 ender_pearl + 1 blaze_powder each, make 12)

PHASE 4 — THE END:
12. find_structure("stronghold") to locate the stronghold
13. Go to stronghold, find end portal room
14. enter_portal to enter The End
15. attack("ender_dragon") — KEEP ATTACKING until dragon is dead. This is the WIN.

RULES:
- 1 log = 4 planks
- Mine 'stone' to get cobblestone
- SKIP diamonds — go straight to nether after iron tools. Diamonds waste time and you die in caves.
- If you die, rebuild iron tools FAST and continue from where you left off
- Craft a sword before entering the nether — blazes and endermen will kill you without one
- The dragon has 200 HP — keep calling attack("ender_dragon") until it dies
- NEVER give up. If something fails, try a different approach. The goal is ALWAYS: kill the dragon."""

def p(msg):
    print(msg, flush=True)

def run_agent(max_turns=80):
    requests.post(f"{BOT_API}/reset")
    time.sleep(3)
    p("=== MINECRAFT SPEEDRUN AGENT ===\n")

    messages = [{"role": "user", "content": "Speedrun. Go."}]

    for turn in range(max_turns):
        response = client.messages.create(model="claude-opus-4-6", max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                p(f"[T{turn}] {block.text.strip()}")

        if response.stop_reason == "end_turn":
            p("\n[Agent done]")
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                p(f"  T{turn}: {block.name}({json.dumps(block.input, separators=(',',':'))})")
                try:
                    result = execute_tool(block.name, block.input)
                    rd = json.loads(result)
                    completed = rd.get("newly_completed", [])
                    if completed:
                        p(f"       *** COMPLETED: {completed} ***")
                    r = rd.get("result", {})
                    if isinstance(r, dict) and r.get("success") is False:
                        p(f"       FAIL: {r.get('error','?')}")
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                except Exception as e:
                    p(f"       ERROR: {e}")
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {e}", "is_error": True})

        messages.append({"role": "user", "content": tool_results})

    state = requests.get(f"{BOT_API}/state").json()
    p(f"\n{'='*50}")
    p(f"Objectives ({len(state['objectives_completed'])}): {state['objectives_completed']}")
    p(f"HP: {state['health']}/20 | Dim: {state['dimension']} | Time: {state['elapsed_seconds']}s")

if __name__ == "__main__":
    run_agent()
