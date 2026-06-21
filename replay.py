"""Fast replay of the dragon speedrun — fires actions with minimal delay."""
import requests, time, sys

BOT = "http://localhost:3001"
DELAY = 1.5  # seconds between actions

def act(endpoint, data=None, timeout=120):
    try:
        if data is None:
            r = requests.post(f"{BOT}/action/{endpoint}", json={}, timeout=timeout)
        else:
            r = requests.post(f"{BOT}/action/{endpoint}", json=data, timeout=timeout)
        result = r.json()
        obj = result.get("state", result).get("objectives_completed", [])
        hp = result.get("state", result).get("health", "?")
        dim = result.get("state", result).get("dimension", "?")
        print(f"  {endpoint}({data or {}}) -> HP:{hp} Dim:{dim} Obj:{len(obj)}", flush=True)
        return result
    except Exception as e:
        print(f"  {endpoint} ERROR: {e}", flush=True)
        return {}

def phase(name):
    print(f"\n{'='*50}", flush=True)
    print(f"  {name}", flush=True)
    print(f"{'='*50}", flush=True)
    time.sleep(0.5)

def step(desc, endpoint, data=None, timeout=120):
    print(f"\n> {desc}", flush=True)
    time.sleep(DELAY)
    return act(endpoint, data, timeout)

# Reset
print("=== MINECRAFT SPEEDRUN REPLAY ===", flush=True)
print(f"Watch live at http://localhost:3007", flush=True)
print(f"Action delay: {DELAY}s\n", flush=True)
requests.post(f"{BOT}/reset")
time.sleep(3)

# PHASE 1: Overworld Tools
phase("PHASE 1: OVERWORLD TOOLS")
step("Looking around...", "look_around")
step("Mining 5 oak logs", "mine", {"block_name": "oak_log", "count": 5})
step("Crafting 5 planks", "craft", {"item_name": "oak_planks", "count": 5})
step("Crafting crafting table", "craft", {"item_name": "crafting_table"})
step("Crafting sticks", "craft", {"item_name": "stick", "count": 2})
step("Crafting wooden pickaxe", "craft", {"item_name": "wooden_pickaxe"})
step("Equipping wooden pickaxe", "equip", {"item_name": "wooden_pickaxe"})
step("Mining 11 stone", "mine", {"block_name": "stone", "count": 11})
step("Crafting stone pickaxe", "craft", {"item_name": "stone_pickaxe"})
step("Crafting furnace", "craft", {"item_name": "furnace"})
step("Equipping stone pickaxe", "equip", {"item_name": "stone_pickaxe"})
step("Mining 5 iron ore", "mine", {"block_name": "iron_ore", "count": 5})
step("Mining 5 coal", "mine", {"block_name": "coal_ore", "count": 5})
step("Smelting iron", "smelt", {"item_name": "raw_iron", "fuel": "coal", "count": 5})
step("Crafting iron pickaxe", "craft", {"item_name": "iron_pickaxe"})
step("Crafting iron sword", "craft", {"item_name": "iron_sword"})
step("Equipping iron sword", "equip", {"item_name": "iron_sword"})

# PHASE 2: Nether
phase("PHASE 2: THE NETHER")
step("Building nether portal", "build_nether_portal")
step("Entering portal...", "enter_portal")
step("Finding fortress...", "find_structure", {"name": "fortress"})

# Get fortress coords from response, goto
state = requests.get(f"{BOT}/state").json()
print(f"\n  Current dimension: {state['dimension']}", flush=True)

step("Teleporting to fortress", "goto", {"x": -560, "y": 63, "z": -320})
step("Looking for blazes...", "look_around")
step("Attacking blaze!", "attack", {"entity_name": "blaze"})
step("Attacking blaze!", "attack", {"entity_name": "blaze"})
step("Attacking blaze!", "attack", {"entity_name": "blaze"})
step("Attacking blaze!", "attack", {"entity_name": "blaze"})

# Check blaze rod count
state = requests.get(f"{BOT}/state").json()
inv = {i['name']: i['count'] for i in state['inventory']}
rods = inv.get('blaze_rod', 0)
print(f"\n  Blaze rods: {rods}", flush=True)

step("Crafting blaze powder", "craft", {"item_name": "blaze_powder", "count": 6})

# PHASE 3: Ender Pearls
phase("PHASE 3: ENDER PEARLS")
step("Hunting enderman", "attack", {"entity_name": "enderman"})
step("Hunting enderman", "attack", {"entity_name": "enderman"})
step("Hunting enderman", "attack", {"entity_name": "enderman"})
step("Hunting enderman", "attack", {"entity_name": "enderman"})
step("Hunting enderman", "attack", {"entity_name": "enderman"})
step("Hunting enderman", "attack", {"entity_name": "enderman"})

state = requests.get(f"{BOT}/state").json()
inv = {i['name']: i['count'] for i in state['inventory']}
pearls = inv.get('ender_pearl', 0)
print(f"\n  Ender pearls: {pearls}", flush=True)

step("Crafting eyes of ender", "craft", {"item_name": "ender_eye", "count": 12})

# PHASE 4: The End
phase("PHASE 4: THE END")
step("Finding stronghold...", "find_structure", {"name": "stronghold"})
step("Teleporting to stronghold", "goto", {"x": 0, "y": 30, "z": 0})
step("Entering The End...", "enter_portal")
step("KILLING THE DRAGON!", "attack", {"entity_name": "ender_dragon"}, timeout=300)

# Final state
phase("FINAL RESULTS")
state = requests.get(f"{BOT}/state").json()
obj = state['objectives_completed']
print(f"  Objectives: {len(obj)}/16", flush=True)
for o in obj:
    print(f"    ✓ {o}", flush=True)
print(f"  HP: {state['health']}/20", flush=True)
print(f"  Dimension: {state['dimension']}", flush=True)
print(f"\n=== SPEEDRUN COMPLETE ===", flush=True)
