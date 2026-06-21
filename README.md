# DragonSlayer

An AI agent that speedruns Minecraft — from punching its first tree to killing the Ender Dragon. No human input, no hardcoded paths. The agent observes, thinks, and acts on its own, learning to navigate one of the most complex open-world games ever made.

Built at the [HUD x YC Frontier RL Environments Hackathon](https://www.hud.ai/hackathon) (June 2026).

## What is this?

We built a full reinforcement learning environment around Minecraft speedrunning, then trained an agent to play it.

The agent connects to a real Minecraft server and plays the game through text — no pixels, no screen, no 3D vision. It gets a snapshot of its position, health, inventory, nearby blocks, and entities. From that, it decides what to do next: mine oak logs, craft a pickaxe, smelt iron, build a nether portal, fight blazes, hunt endermen, find a stronghold, and ultimately kill the Ender Dragon.

That's 16 milestones across three dimensions, dozens of crafting recipes, hostile mobs, lava lakes, and a flying boss fight — all driven by an AI reading text.

## How it works

There are three layers:

**1. The Minecraft Bot** (`bot.js`)

A [Mineflayer](https://github.com/PrismarineJS/mineflayer) bot that connects to a vanilla Minecraft 1.20.4 server and exposes 13 actions through an HTTP API:

- `mine` — find and break blocks
- `craft` — craft items using recipes
- `smelt` — smelt ores in a furnace
- `equip` — equip tools and weapons
- `goto` — navigate to coordinates (sprint pathfinding in 40-block chunks)
- `attack` — fight mobs, including flying ones like the Ender Dragon
- `dig_to_y` — dig down to a target depth
- `get_obsidian` — the classic speedrun move: bucket water onto lava, mine the obsidian
- `build_nether_portal` — place obsidian blocks and light the portal
- `enter_portal` — walk into a portal and change dimensions
- `find_structure` — locate fortresses, strongholds, villages

The bot handles all the low-level Minecraft mechanics so the agent can focus on strategy.

**2. The RL Environment** (`env.py`)

A [HUD](https://www.hud.ai) environment that wraps the bot API and defines:

- **16 speedrun objectives** across easy, medium, and hard tiers
- **Shaped rewards** — partial credit for each milestone, time bonuses for speed
- **4 task templates** — from "craft a wooden pickaxe" to "full speedrun"
- **MCP tool integration** so any compatible agent can plug in

The reward calibration targets 20-50% average with real variance — hard enough to be interesting, achievable enough to learn from.

**3. The Training Pipeline** (`train.py`)

Collects gameplay trajectories by running [Gemma-3](https://ai.google.dev/gemma) through [Fireworks AI](https://fireworks.ai), then post-trains with GRPO (Group Relative Policy Optimization) using LoRA. The loop:

1. Agent plays Minecraft, we record every (state, action, reward) tuple
2. Group trajectories, compute relative advantages
3. Update the policy with clipped gradients
4. Repeat

## The speedrun

A typical successful run looks like this:

1. **Overworld tools** (~5 min) — Punch trees, craft planks, make a crafting table, wooden pickaxe, stone pickaxe, furnace, iron tools
2. **Diamond mining** (~10 min) — Dig to Y=11, find diamond ore, craft a diamond pickaxe
3. **Nether prep** (~5 min) — Craft a bucket, pour water on lava to make obsidian, build and light a portal
4. **Nether** (~10 min) — Find a fortress, fight blazes for blaze rods
5. **Ender pearls** (~10 min) — Hunt endermen, craft eyes of ender
6. **The End** (~5 min) — Find the stronghold, activate the portal, fight the Ender Dragon

Full run: ~45 minutes. The game runs at 10x tick speed, so the agent's thinking time is the bottleneck, not Minecraft's simulation.

## Running it yourself

**Prerequisites:**
- Minecraft Java Edition server 1.20.4 (drop `server.jar` in `server/`)
- Node.js 18+
- Python 3.10+

**Start the server:**
```bash
cd server
java -Xmx2G -jar server.jar nogui
```

**Start the bot:**
```bash
npm install
node bot.js
```

**Run the agent (via API):**
```bash
# Check state
curl http://localhost:3001/state

# Take an action
curl -X POST http://localhost:3001/action \
  -H "Content-Type: application/json" \
  -d '{"action": "mine", "args": ["oak_log", 5]}'

# Reset for a new run
curl -X POST http://localhost:3001/reset
```

**Train with Gemma:**
```bash
pip install torch transformers peft
export FIREWORKS_API_KEY=your_key

# Collect trajectories
python train.py --model google/gemma-3-4b-it --backend fireworks --collect-only

# Train
python train.py --model google/gemma-3-4b-it --epochs 3
```

**Watch the bot play:**

Join `localhost:25565` in Minecraft 1.20.4, then:
```
/gamemode spectator
/spectate SpeedrunBot
```

You'll follow the bot in first person as it plays. When it changes dimensions, you follow automatically.

## Tech stack

- **Mineflayer** — Minecraft bot framework
- **Gemma-3** — Base model for the agent (via Google DeepMind)
- **Fireworks AI** — Fast inference for trajectory collection
- **HUD** — RL environment platform
- **GRPO + LoRA** — Post-training with parameter-efficient fine-tuning

## What we learned

Minecraft is a brutally hard RL problem. The state space is enormous, the action space is combinatorial, and a single mistake (falling in lava, getting blown up by a creeper) can end a run. The agent has to maintain a multi-step plan across three dimensions while reacting to a world that's actively trying to kill it.

The hardest part wasn't the training — it was making the environment reliable enough that the agent could actually learn. Mineflayer's crafting API is buggy, pathfinding breaks in the Nether, mob spawning is unreliable, and portal transitions are flaky. Most of our time went into making the 13 actions robust enough that failures were the agent's fault, not the environment's.

The Ender Dragon fight is still the weakest link. It's a flying mob that only comes close during dive attacks, and the bot can only melee. But it works — the agent stands on the obsidian platform, watches the dragon circle, and swings when it's in range.

## License

MIT
