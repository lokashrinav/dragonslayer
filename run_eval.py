"""Local evaluation runner — tests MCP tools against the live bot without HUD API key.

Usage:
    python run_eval.py                  # Run all tasks
    python run_eval.py --task get_wood  # Run specific task
    python run_eval.py --auto           # Auto-execute speedrun strategy (no LLM)
"""

import asyncio
import json
import sys
import time

import requests

BOT_API = "http://127.0.0.1:3001"


async def auto_speedrun_easy():
    """Execute the wooden pickaxe strategy automatically to test tools."""
    from env import mine, craft, place, look_around

    requests.post(f"{BOT_API}/reset")
    start = time.time()

    print("Step 1: Look around...")
    state = await look_around()
    print(state[:200])
    print()

    print("Step 2: Mine 6 logs...")
    result = await mine("log", 6)
    print(result[:200])
    print()

    print("Step 3: Craft planks x3...")
    for i in range(3):
        result = await craft("planks", 1)
    print(result[:200])
    print()

    print("Step 4: Craft crafting table...")
    result = await craft("crafting_table", 1)
    print(result[:200])
    print()

    print("Step 5: Craft sticks...")
    result = await craft("stick", 1)
    print(result[:200])
    print()

    print("Step 6: Craft wooden pickaxe...")
    result = await craft("wooden_pickaxe", 1)
    print(result[:200])
    print()

    elapsed = time.time() - start

    # Check final state
    r = requests.get(f"{BOT_API}/state")
    state = r.json()
    completed = state.get("objectives_completed", [])

    print("=" * 50)
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Objectives: {completed}")
    print(f"Total reward points: {state.get('total_reward', 0)}")

    from env import compute_reward

    for obj_id in ["get_wood", "craft_planks", "craft_crafting_table", "craft_wooden_pickaxe"]:
        r = compute_reward(obj_id, obj_id in completed, state.get("elapsed_seconds", elapsed))
        print(f"  {obj_id}: reward={r:.3f}")

    return completed


async def auto_speedrun_medium():
    """Execute the iron pickaxe strategy automatically."""
    from env import mine, craft, place, smelt, look_around, equip

    requests.post(f"{BOT_API}/reset")

    print("=== MEDIUM SPEEDRUN: Iron Pickaxe ===")
    print()

    steps = [
        ("Mine logs", lambda: mine("log", 6)),
        ("Craft planks", lambda: craft("planks", 6)),
        ("Craft crafting table", lambda: craft("crafting_table", 1)),
        ("Place crafting table", lambda: place("crafting_table")),
        ("Craft sticks", lambda: craft("stick", 4)),
        ("Craft wooden pickaxe", lambda: craft("wooden_pickaxe", 1)),
        ("Equip wooden pickaxe", lambda: equip("wooden_pickaxe")),
        ("Mine cobblestone", lambda: mine("cobblestone", 11)),
        ("Craft stone pickaxe", lambda: craft("stone_pickaxe", 1)),
        ("Craft furnace", lambda: craft("furnace", 1)),
        ("Place furnace", lambda: place("furnace")),
        ("Equip stone pickaxe", lambda: equip("stone_pickaxe")),
        ("Mine iron ore", lambda: mine("iron_ore", 3)),
        ("Mine coal", lambda: mine("coal_ore", 3)),
        ("Smelt iron", lambda: smelt("raw_iron", "coal", 3)),
        ("Craft iron pickaxe", lambda: craft("iron_pickaxe", 1)),
    ]

    start = time.time()
    for i, (name, action) in enumerate(steps, 1):
        print(f"Step {i}: {name}...")
        result = await action()
        success = "success" in result.lower() or "OBJECTIVES" in result
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {result[:150]}")
        if "FAIL" in status and "mine" not in name.lower():
            print(f"  Stopping — {name} failed")
            break
        print()

    elapsed = time.time() - start
    r = requests.get(f"{BOT_API}/state")
    state = r.json()
    completed = state.get("objectives_completed", [])

    print("=" * 50)
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Objectives: {completed}")
    print(f"Total reward points: {state.get('total_reward', 0)}")

    return completed


if __name__ == "__main__":
    import os
    os.environ["PYTHONIOENCODING"] = "utf-8"

    if "--medium" in sys.argv:
        asyncio.run(auto_speedrun_medium())
    else:
        asyncio.run(auto_speedrun_easy())
