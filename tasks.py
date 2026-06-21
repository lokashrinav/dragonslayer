"""Minecraft Speedrun task variants — 10 tasks spanning the difficulty ladder.

Real speedrun reference times (Any% Glitchless):
- World record: ~8 minutes
- Good run: ~15 minutes
- Casual: ~45 minutes

Our tasks test subsections of the speedrun at calibrated difficulty:
- Easy (60-90% expected): basic resource gathering and crafting
- Medium (20-50% expected): multi-step tool progression
- Hard (5-15% expected): deep mining, nether access
"""

from env import speedrun_easy, speedrun_medium, speedrun_hard, speedrun_full

# ============================================================================
# EASY TIER — high success rate, fast tasks
# Expected: 60-90% reward, 1-3 minutes per run
# ============================================================================

# Task 1: Punch a tree — most basic Minecraft action
task_get_wood = speedrun_easy(objective="get_wood")

# Task 2: Full early-game crafting chain
task_craft_planks = speedrun_easy(objective="craft_planks")

# Task 3: Make a crafting table — first real milestone
task_craft_table = speedrun_easy(objective="craft_crafting_table")

# Task 4: Wooden pickaxe — complete tool chain
task_wooden_pickaxe = speedrun_easy(objective="craft_wooden_pickaxe")

# ============================================================================
# MEDIUM TIER — moderate success rate, requires planning
# Expected: 20-50% reward, 3-10 minutes per run
# ============================================================================

# Task 5: Mine cobblestone — requires wooden pickaxe first
task_cobblestone = speedrun_medium(objective="get_cobblestone")

# Task 6: Stone pickaxe — tool upgrade chain
task_stone_pickaxe = speedrun_medium(objective="craft_stone_pickaxe")

# Task 7: Iron pickaxe — full early-game progression
# Requires: wood → planks → table → wooden pick → cobble → stone pick
#           → iron ore → furnace → smelt → iron pick
task_iron_pickaxe = speedrun_medium(objective="craft_iron_pickaxe")

# ============================================================================
# HARD TIER — low success rate, complex multi-step
# Expected: 5-15% reward, 10-30 minutes per run
# ============================================================================

# Task 8: Mine diamonds — deep mining at Y=-59
task_diamonds = speedrun_hard(objective="get_diamonds")

# Task 9: Enter the nether — build obsidian portal
task_nether = speedrun_hard(objective="enter_nether")

# ============================================================================
# FULL SPEEDRUN — cumulative scoring across all objectives
# Expected: 20-40% reward (partial completion), 15-30 minutes per run
# ============================================================================

# Task 10: Full speedrun — maximize objectives in time
task_full_speedrun = speedrun_full()
