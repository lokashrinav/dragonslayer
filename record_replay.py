"""Record a fast replay of the Minecraft speedrun as video."""
import asyncio, requests, time
from playwright.async_api import async_playwright

BOT = "http://localhost:3001"
DELAY = 0.3

def act(action, args=None, timeout=120):
    try:
        payload = {"action": action, "args": args or []}
        r = requests.post(f"{BOT}/action", json=payload, timeout=timeout)
        result = r.json()
        s = result.get("state", {})
        obj = s.get("objectives_completed", [])
        hp = s.get("health", "?")
        dim = s.get("dimension", "?")
        print(f"  [{len(obj):>2}/16] {action}({args or []}) HP:{hp} {dim}", flush=True)
        return result
    except Exception as e:
        print(f"  {action} ERROR: {e}", flush=True)
        return {}

def step(desc, action, args=None, timeout=120):
    print(f"> {desc}", flush=True)
    time.sleep(DELAY)
    return act(action, args, timeout)

def run_speedrun():
    print("\n=== SPEEDRUN START ===\n", flush=True)
    requests.post(f"{BOT}/reset")
    time.sleep(3)

    # Phase 1: Overworld Tools
    print("--- PHASE 1: TOOLS ---", flush=True)
    step("Look around", "look_around")
    step("Mine 5 oak logs", "mine", ["oak_log", 5])
    step("Craft planks", "craft", ["oak_planks", 5])
    step("Craft table", "craft", ["crafting_table"])
    step("Craft sticks", "craft", ["stick", 2])
    step("Craft wood pick", "craft", ["wooden_pickaxe"])
    step("Equip wood pick", "equip", ["wooden_pickaxe"])
    step("Mine 11 stone", "mine", ["stone", 11])
    step("Craft stone pick", "craft", ["stone_pickaxe"])
    step("Craft furnace", "craft", ["furnace"])
    step("Equip stone pick", "equip", ["stone_pickaxe"])
    step("Mine 5 iron ore", "mine", ["iron_ore", 5])
    step("Mine 5 coal", "mine", ["coal_ore", 5])
    step("Smelt iron", "smelt", ["raw_iron", "coal", 5])
    step("Craft iron pick", "craft", ["iron_pickaxe"])
    step("Craft iron sword", "craft", ["iron_sword"])
    step("Equip sword", "equip", ["iron_sword"])

    # Phase 2: Nether
    print("\n--- PHASE 2: NETHER ---", flush=True)
    step("Build nether portal", "build_nether_portal")
    step("Enter portal", "enter_portal")
    time.sleep(3)
    step("Find fortress", "find_structure", ["fortress"])
    step("TP to fortress", "goto", [-560, 63, -320])
    step("Look around fortress", "look_around")
    for i in range(7):
        step(f"Attack blaze #{i+1}", "attack", ["blaze"])
    step("Craft blaze powder", "craft", ["blaze_powder", 6])

    # Phase 3: Ender Pearls
    print("\n--- PHASE 3: ENDER PEARLS ---", flush=True)
    for i in range(12):
        step(f"Hunt enderman #{i+1}", "attack", ["enderman"])
    step("Craft eyes of ender", "craft", ["ender_eye", 12])

    # Phase 4: The End
    print("\n--- PHASE 4: THE END ---", flush=True)
    step("Find stronghold", "find_structure", ["stronghold"])
    step("TP to stronghold", "goto", [0, 30, 0])
    step("Enter The End", "enter_portal")
    step("KILL THE DRAGON", "attack", ["ender_dragon"], timeout=300)

    # Final
    state = requests.get(f"{BOT}/state").json()
    obj = state["objectives_completed"]
    print(f"\n=== DONE: {len(obj)}/16 objectives ===", flush=True)
    for o in obj:
        print(f"  + {o}", flush=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="C:/Users/lokas/mc-speedrun-rl/recordings",
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto("http://localhost:3007")
        await page.wait_for_timeout(3000)

        print("Recording started...", flush=True)
        run_speedrun()

        await page.wait_for_timeout(2000)
        await context.close()
        await browser.close()

        print("\nVideo saved to C:/Users/lokas/mc-speedrun-rl/recordings/", flush=True)

asyncio.run(main())
