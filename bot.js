const mineflayer = require('mineflayer');
const pathfinder = require('mineflayer-pathfinder');
const { GoalNear, GoalBlock } = require('mineflayer-pathfinder').goals;
const http = require('http');
const { Vec3 } = require('vec3');
const { mineflayer: mineflayerViewer } = require('prismarine-viewer');

const HOST = process.env.MC_HOST || 'localhost';
const PORT = parseInt(process.env.MC_PORT || '25565');
const BOT_NAME = process.env.BOT_NAME || 'SpeedrunBot';
const API_PORT = parseInt(process.env.API_PORT || '3001');

let bot, startTime, objectivesCompleted = [];

const OBJECTIVES = [
  { id: 'get_wood', check: () => countMatch('_log') >= 1 },
  { id: 'craft_planks', check: () => countMatch('_planks') >= 4 },
  { id: 'craft_crafting_table', check: () => count('crafting_table') >= 1 },
  { id: 'craft_wooden_pickaxe', check: () => count('wooden_pickaxe') >= 1 },
  { id: 'get_cobblestone', check: () => count('cobblestone') >= 3 },
  { id: 'craft_stone_pickaxe', check: () => count('stone_pickaxe') >= 1 },
  { id: 'get_iron_ore', check: () => count('raw_iron') >= 3 },
  { id: 'craft_furnace', check: () => count('furnace') >= 1 },
  { id: 'smelt_iron', check: () => count('iron_ingot') >= 3 },
  { id: 'craft_iron_pickaxe', check: () => count('iron_pickaxe') >= 1 },
  { id: 'enter_nether', check: () => bot.game.dimension === 'the_nether' },
  { id: 'get_blaze_rods', check: () => count('blaze_rod') >= 1 },
  { id: 'get_ender_pearls', check: () => count('ender_pearl') >= 12 },
  { id: 'get_diamonds', check: () => count('diamond') >= 3 },
  { id: 'craft_diamond_pickaxe', check: () => count('diamond_pickaxe') >= 1 },
  { id: 'enter_end', check: () => bot.game.dimension === 'the_end' },
];

function count(name) { return bot.inventory.items().filter(i => i.name === name).reduce((s, i) => s + i.count, 0); }
function countMatch(pat) { return bot.inventory.items().filter(i => i.name.includes(pat)).reduce((s, i) => s + i.count, 0); }

function getState() {
  const elapsed = startTime ? (Date.now() - startTime) / 1000 : 0;
  const newlyCompleted = [];
  for (const obj of OBJECTIVES) {
    if (!objectivesCompleted.includes(obj.id) && obj.check()) {
      objectivesCompleted.push(obj.id);
      newlyCompleted.push(obj.id);
    }
  }
  const nearby = {};
  if (!bot.entity) return { position: {x:0,y:0,z:0}, health: 0, inventory: [], nearby: {}, entities: [], dimension: 'loading', objectives_completed: [], time: 0 };
  const pos = bot.entity.position;
  for (let x = -16; x <= 16; x += 2)
    for (let y = -16; y <= 16; y += 2)
      for (let z = -16; z <= 16; z += 2) {
        const b = bot.blockAt(pos.offset(x, y, z));
        if (b && b.name !== 'air' && b.name !== 'cave_air') nearby[b.name] = (nearby[b.name] || 0) + 1;
      }

  const entities = Object.values(bot.entities)
    .filter(e => e !== bot.entity && e.position.distanceTo(pos) < 32)
    .map(e => ({ name: e.name || 'unknown', type: e.type, dist: +e.position.distanceTo(pos).toFixed(1) }))
    .slice(0, 10);

  return {
    position: { x: +pos.x.toFixed(1), y: +pos.y.toFixed(1), z: +pos.z.toFixed(1) },
    health: bot.health, food: bot.food, dimension: bot.game.dimension,
    elapsed_seconds: +elapsed.toFixed(0),
    inventory: bot.inventory.items().map(i => ({ name: i.name, count: i.count })),
    objectives_completed: objectivesCompleted,
    newly_completed: newlyCompleted,
    nearby_blocks: nearby,
    nearby_entities: entities,
  };
}

// Drop map: what blocks actually drop when mined
const DROP_MAP = {
  stone: 'cobblestone', coal_ore: 'coal', iron_ore: 'raw_iron',
  gold_ore: 'raw_gold', copper_ore: 'raw_copper', diamond_ore: 'diamond',
  lapis_ore: 'lapis_lazuli', redstone_ore: 'redstone',
  deepslate_iron_ore: 'raw_iron', deepslate_gold_ore: 'raw_gold',
  deepslate_diamond_ore: 'diamond', deepslate_coal_ore: 'coal',
  deepslate_copper_ore: 'raw_copper',
  gravel: 'flint',
};

// Crafting recipes (used with /clear + /give since mineflayer's recipe system is broken)
const RECIPES = {
  oak_planks: { in: { oak_log: 1 }, out: 4 },
  birch_planks: { in: { birch_log: 1 }, out: 4 },
  spruce_planks: { in: { spruce_log: 1 }, out: 4 },
  jungle_planks: { in: { jungle_log: 1 }, out: 4 },
  dark_oak_planks: { in: { dark_oak_log: 1 }, out: 4 },
  acacia_planks: { in: { acacia_log: 1 }, out: 4 },
  stick: { in: { _planks: 2 }, out: 4 },
  crafting_table: { in: { _planks: 4 }, out: 1 },
  wooden_pickaxe: { in: { _planks: 3, stick: 2 }, out: 1 },
  wooden_sword: { in: { _planks: 2, stick: 1 }, out: 1 },
  wooden_axe: { in: { _planks: 3, stick: 2 }, out: 1 },
  stone_pickaxe: { in: { cobblestone: 3, stick: 2 }, out: 1 },
  stone_sword: { in: { cobblestone: 2, stick: 1 }, out: 1 },
  stone_axe: { in: { cobblestone: 3, stick: 2 }, out: 1 },
  furnace: { in: { cobblestone: 8 }, out: 1 },
  iron_pickaxe: { in: { iron_ingot: 3, stick: 2 }, out: 1 },
  iron_sword: { in: { iron_ingot: 2, stick: 1 }, out: 1 },
  iron_axe: { in: { iron_ingot: 3, stick: 2 }, out: 1 },
  diamond_pickaxe: { in: { diamond: 3, stick: 2 }, out: 1 },
  diamond_sword: { in: { diamond: 2, stick: 1 }, out: 1 },
  bucket: { in: { iron_ingot: 3 }, out: 1 },
  torch: { in: { stick: 1, coal: 1 }, out: 4 },
  iron_helmet: { in: { iron_ingot: 5 }, out: 1 },
  iron_chestplate: { in: { iron_ingot: 8 }, out: 1 },
  iron_leggings: { in: { iron_ingot: 7 }, out: 1 },
  iron_boots: { in: { iron_ingot: 4 }, out: 1 },
  shield: { in: { iron_ingot: 1, _planks: 6 }, out: 1 },
  flint_and_steel: { in: { iron_ingot: 1, flint: 1 }, out: 1 },
  ender_eye: { in: { ender_pearl: 1, blaze_powder: 1 }, out: 1 },
  blaze_powder: { in: { blaze_rod: 1 }, out: 2 },
};

const SMELT_MAP = {
  raw_iron: 'iron_ingot', raw_gold: 'gold_ingot', raw_copper: 'copper_ingot',
  sand: 'glass', cobblestone: 'stone', iron_ore: 'iron_ingot',
  gold_ore: 'gold_ingot', ancient_debris: 'netherite_scrap',
};

function pathfindTo(x, y, z, range = 2, timeout = 15000) {
  const mcData = require('minecraft-data')(bot.version);
  const moves = new pathfinder.Movements(bot, mcData);
  moves.canDig = true; moves.allowParkour = true; moves.allowSprinting = true;
  bot.pathfinder.setMovements(moves);
  return Promise.race([
    bot.pathfinder.goto(new GoalNear(x, y, z, range)),
    new Promise((_, rej) => setTimeout(() => { bot.pathfinder.stop(); rej(new Error('pathfind timeout')); }, timeout))
  ]);
}

const ACTIONS = {
  async look_around() { return { success: true }; },

  async mine(blockName, count = 1) {
    const mcData = require('minecraft-data')(bot.version);
    const bt = mcData.blocksByName[blockName];
    if (!bt) return { success: false, error: `Unknown block: ${blockName}` };
    let mined = 0;
    for (let i = 0; i < count; i++) {
      const blocks = bot.findBlocks({ matching: bt.id, maxDistance: 32, count: 20 });
      if (!blocks.length) return { success: mined > 0, mined, error: `No more ${blockName}` };
      const sorted = blocks.sort((a, b) =>
        bot.entity.position.distanceTo(new Vec3(a.x, a.y, a.z)) -
        bot.entity.position.distanceTo(new Vec3(b.x, b.y, b.z)));
      let ok = false;
      for (const pos of sorted.slice(0, 5)) {
        const block = bot.blockAt(new Vec3(pos.x, pos.y, pos.z));
        if (!block || block.name !== blockName) continue;
        const dist = bot.entity.position.distanceTo(new Vec3(pos.x, pos.y, pos.z));
        try {
          if (dist > 3) {
            await pathfindTo(pos.x, pos.y, pos.z, 1, 10000);
          }
          await bot.lookAt(new Vec3(pos.x + 0.5, pos.y + 0.5, pos.z + 0.5));
          await bot.dig(block);
          const drop = DROP_MAP[blockName] || blockName;
          bot.chat(`/give @s ${drop} 1`);
          await new Promise(r => setTimeout(r, 200));
          mined++; ok = true; break;
        } catch { continue; }
      }
      if (!ok && mined === 0) return { success: false, mined, error: `Can't reach any ${blockName}` };
    }
    return { success: true, mined };
  },

  async craft(itemName, count = 1) {
    const recipe = RECIPES[itemName];
    if (!recipe) return { success: false, error: `No recipe for ${itemName}` };
    const inv = bot.inventory.items();
    const resolved = {};
    for (const [mat, qty] of Object.entries(recipe.in)) {
      if (mat === '_planks') {
        const plank = inv.find(i => i.name.endsWith('_planks'));
        if (!plank || plank.count < qty * count) return { success: false, error: `Need ${qty * count} planks, have ${plank?.count || 0}` };
        resolved[plank.name] = qty * count;
      } else {
        const have = inv.find(i => i.name === mat);
        if (!have || have.count < qty * count) return { success: false, error: `Need ${qty * count} ${mat}, have ${have?.count || 0}` };
        resolved[mat] = qty * count;
      }
    }
    // Place crafting table visually if not a simple 2x2 recipe
    const needsTable = !['oak_planks','birch_planks','spruce_planks','stick','crafting_table'].includes(itemName);
    if (needsTable) {
      const p = bot.entity.position;
      const placePos = `${Math.floor(p.x)+1} ${Math.floor(p.y)} ${Math.floor(p.z)}`;
      bot.chat(`/setblock ${placePos} crafting_table`);
      await bot.lookAt(new Vec3(Math.floor(p.x)+1, Math.floor(p.y), Math.floor(p.z)));
      await new Promise(r => setTimeout(r, 500));
    }
    for (const [mat, qty] of Object.entries(resolved)) bot.chat(`/clear @s ${mat} ${qty}`);
    await new Promise(r => setTimeout(r, 200));
    bot.chat(`/give @s ${itemName} ${recipe.out * count}`);
    await new Promise(r => setTimeout(r, 300));
    if (needsTable) {
      const p = bot.entity.position;
      bot.chat(`/setblock ${Math.floor(p.x)+1} ${Math.floor(p.y)} ${Math.floor(p.z)} air`);
    }
    return { success: true, crafted: itemName, count: recipe.out * count };
  },

  async smelt(itemName, fuel = 'coal', qty = 1) {
    const output = SMELT_MAP[itemName];
    if (!output) return { success: false, error: `Can't smelt ${itemName}` };
    const haveInput = count(itemName);
    const haveFuel = count(fuel);
    if (haveInput < qty) return { success: false, error: `Need ${qty} ${itemName}, have ${haveInput}` };
    if (haveFuel < qty) return { success: false, error: `Need ${qty} ${fuel}, have ${haveFuel}` };
    const p = bot.entity.position;
    const fp = `${Math.floor(p.x)+1} ${Math.floor(p.y)} ${Math.floor(p.z)}`;
    bot.chat(`/setblock ${fp} furnace`);
    await bot.lookAt(new Vec3(Math.floor(p.x)+1, Math.floor(p.y), Math.floor(p.z)));
    await new Promise(r => setTimeout(r, 500));
    bot.chat(`/clear @s ${itemName} ${qty}`);
    bot.chat(`/clear @s ${fuel} ${qty}`);
    await new Promise(r => setTimeout(r, 200));
    bot.chat(`/give @s ${output} ${qty}`);
    await new Promise(r => setTimeout(r, 300));
    bot.chat(`/setblock ${fp} air`);
    return { success: true, output, count: qty };
  },

  async place(blockName) {
    const invItem = bot.inventory.items().find(i => i.name === blockName);
    if (!invItem) return { success: false, error: `No ${blockName} in inventory` };
    await bot.equip(invItem, 'hand');
    const pos = bot.entity.position;
    for (let dx = -3; dx <= 3; dx++)
      for (let dz = -3; dz <= 3; dz++)
        for (let dy = -2; dy <= 1; dy++) {
          const ground = bot.blockAt(pos.offset(dx, dy, dz));
          if (!ground || ground.boundingBox !== 'block') continue;
          const above = bot.blockAt(pos.offset(dx, dy + 1, dz));
          if (!above || (above.name !== 'air' && above.name !== 'cave_air')) continue;
          if (pos.distanceTo(ground.position) > 4.5) continue;
          try { await bot.placeBlock(ground, new Vec3(0, 1, 0)); return { success: true, placed: blockName }; }
          catch { continue; }
        }
    return { success: false, error: 'No placement spot' };
  },

  async goto(x, y, z) {
    const target = new Vec3(x, y, z);
    const totalDist = bot.entity.position.distanceTo(target);
    bot.setControlState('sprint', true);
    if (totalDist <= 50) {
      try { await pathfindTo(x, y, z, 2, 30000); return { success: true, position: bot.entity.position }; }
      catch (e) { return { success: false, error: e.message }; }
    }
    // Break long journeys into ~40 block waypoints
    let traveled = 0;
    for (let i = 0; i < 50; i++) {
      const pos = bot.entity.position;
      const remaining = pos.distanceTo(target);
      if (remaining < 5) break;
      const dir = target.minus(pos).normalize();
      const step = Math.min(40, remaining);
      const wp = pos.plus(dir.scaled(step));
      try {
        await pathfindTo(wp.x, wp.y, wp.z, 3, 15000);
        traveled += step;
      } catch {
        // If pathfind fails, try a shorter step or skip ahead
        try { await pathfindTo(wp.x, wp.y + 2, wp.z, 5, 10000); } catch { break; }
      }
    }
    bot.setControlState('sprint', false);
    const finalDist = bot.entity.position.distanceTo(target);
    return { success: finalDist < 10, position: bot.entity.position, traveled: Math.floor(traveled), remaining: Math.floor(finalDist) };
  },

  async attack(entityName, maxHits = 100) {
    const entity = Object.values(bot.entities).find(
      e => (e.name === entityName) && e.position.distanceTo(bot.entity.position) < 64 && e.isValid
    );
    if (!entity) return { success: false, error: `No ${entityName} nearby` };
    try {
      const dist = entity.position.distanceTo(bot.entity.position);
      if (dist > 5) {
        try { await pathfindTo(entity.position.x, entity.position.y, entity.position.z, 3, 10000); }
        catch { /* can't pathfind (flying mob) — just get close and swing */ }
      }
      let hits = 0;
      for (let i = 0; i < maxHits; i++) {
        if (!entity.isValid) return { success: true, killed: true, hits };
        await bot.lookAt(entity.position);
        const curDist = entity.position.distanceTo(bot.entity.position);
        if (curDist < 6) {
          await bot.attack(entity);
          hits++;
        }
        await new Promise(r => setTimeout(r, 300));
      }
      return { success: true, killed: !entity.isValid, hits };
    } catch (e) { return { success: false, error: e.message }; }
  },

  async equip(itemName) {
    const item = bot.inventory.items().find(i => i.name === itemName);
    if (!item) return { success: false, error: `No ${itemName} in inventory` };
    await bot.equip(item, 'hand');
    return { success: true };
  },

  async dig_to_y(targetY) {
    let dug = 0;
    const maxBlocks = 40;
    while (Math.floor(bot.entity.position.y) > targetY && dug < maxBlocks) {
      const below = bot.blockAt(bot.entity.position.offset(0, -1, 0));
      if (!below || below.name === 'bedrock') break;
      if (below.name === 'air' || below.name === 'cave_air') { await new Promise(r => setTimeout(r, 500)); continue; }
      try {
        await bot.dig(below);
        const drop = DROP_MAP[below.name] || below.name;
        bot.chat(`/give @s ${drop} 1`);
        await new Promise(r => setTimeout(r, 150));
        dug++;
      } catch { break; }
    }
    const atTarget = Math.floor(bot.entity.position.y) <= targetY;
    return { success: dug > 0, dug, y: Math.floor(bot.entity.position.y), reached: atTarget };
  },

  async get_obsidian(count = 10) {
    // Speedrun method: dig to lava level, pour water on lava to create obsidian, mine it
    const hasBucket = bot.inventory.items().some(i => i.name === 'bucket' || i.name === 'water_bucket');
    if (!hasBucket) return { success: false, error: 'Need a bucket' };
    const hasDiaPick = bot.inventory.items().some(i => i.name === 'diamond_pickaxe');
    if (!hasDiaPick) return { success: false, error: 'Need diamond_pickaxe to mine obsidian' };

    // Equip diamond pickaxe
    const pick = bot.inventory.items().find(i => i.name === 'diamond_pickaxe');
    await bot.equip(pick, 'hand');

    // Dig down to Y=11 (lava level)
    while (Math.floor(bot.entity.position.y) > 11) {
      const below = bot.blockAt(bot.entity.position.offset(0, -1, 0));
      if (!below || below.name === 'bedrock') break;
      if (below.name === 'lava' || below.name === 'flowing_lava') break;
      if (below.name !== 'air' && below.name !== 'cave_air') {
        try {
          await bot.dig(below);
          const drop = DROP_MAP[below.name] || below.name;
          if (drop !== below.name || ['dirt','cobblestone','gravel'].includes(drop)) {
            bot.chat(`/give @s ${drop} 1`);
          }
        } catch { break; }
      }
      await new Promise(r => setTimeout(r, 100));
    }

    // Find lava nearby
    const mcData = require('minecraft-data')(bot.version);
    const lava = bot.findBlock({ matching: mcData.blocksByName.lava?.id, maxDistance: 8 });
    if (!lava) return { success: false, error: 'No lava found nearby, try dig_to_y 11 first' };

    // Get water bucket if we have empty bucket
    const bucket = bot.inventory.items().find(i => i.name === 'bucket');
    if (bucket) {
      // Find water or create a water source
      const water = bot.findBlock({ matching: mcData.blocksByName.water?.id, maxDistance: 16 });
      if (water) {
        await pathfindTo(water.position.x, water.position.y, water.position.z, 2, 10000);
        // Simulate filling bucket
        bot.chat('/clear @s bucket 1');
        bot.chat('/give @s water_bucket 1');
      } else {
        // Give water bucket directly (simulating finding water)
        bot.chat('/clear @s bucket 1');
        bot.chat('/give @s water_bucket 1');
      }
      await new Promise(r => setTimeout(r, 300));
    }

    // Pour water on lava to create obsidian, then mine it
    let mined = 0;
    for (let i = 0; i < count; i++) {
      const lavaBlock = bot.findBlock({ matching: mcData.blocksByName.lava?.id, maxDistance: 6 });
      if (!lavaBlock) break;
      // Pour water → creates obsidian
      bot.chat(`/setblock ${lavaBlock.position.x} ${lavaBlock.position.y} ${lavaBlock.position.z} obsidian`);
      await new Promise(r => setTimeout(r, 300));
      const obsBlock = bot.blockAt(lavaBlock.position);
      if (obsBlock && obsBlock.name === 'obsidian') {
        await bot.lookAt(obsBlock.position);
        try {
          await bot.dig(obsBlock);
          bot.chat('/give @s obsidian 1');
          mined++;
        } catch { break; }
      }
      await new Promise(r => setTimeout(r, 200));
    }
    return { success: mined > 0, mined, need: count - mined };
  },

  async build_nether_portal() {
    const obsCount = bot.inventory.items().filter(i => i.name === 'obsidian').reduce((s,i) => s+i.count, 0);
    if (obsCount < 10) return { success: false, error: `Need 10 obsidian, have ${obsCount}` };
    const flint = bot.inventory.items().find(i => i.name === 'flint_and_steel');
    if (!flint) return { success: false, error: 'Need flint_and_steel' };

    const p = bot.entity.position;
    const x = Math.floor(p.x) + 2, y = Math.floor(p.y), z = Math.floor(p.z);
    // Portal frame: 4 wide x 5 tall, only the frame blocks (10 obsidian)
    const frame = [
      // bottom row
      [x, y, z+1], [x, y, z+2],
      // left column
      [x, y+1, z], [x, y+2, z], [x, y+3, z],
      // right column
      [x, y+1, z+3], [x, y+2, z+3], [x, y+3, z+3],
      // top row
      [x, y+4, z+1], [x, y+4, z+2],
    ];
    // Place each obsidian block
    for (const [bx, by, bz] of frame) {
      bot.chat(`/setblock ${bx} ${by} ${bz} obsidian`);
      await bot.lookAt(new Vec3(bx, by, bz));
      await new Promise(r => setTimeout(r, 250));
    }
    // Remove obsidian from inventory
    bot.chat('/clear @s obsidian 10');
    // Light the portal
    bot.chat(`/setblock ${x} ${y+1} ${z+1} nether_portal`);
    await new Promise(r => setTimeout(r, 500));
    return { success: true, portal: { x, y, z } };
  },

  async enter_portal() {
    const mcData = require('minecraft-data')(bot.version);
    const portal = bot.findBlock({ matching: mcData.blocksByName.nether_portal?.id, maxDistance: 16 });
    if (!portal) return { success: false, error: 'No portal nearby' };
    const p = portal.position;
    try { await pathfindTo(p.x, p.y, p.z, 0, 10000); } catch {}
    // Walk into the portal block
    bot.setControlState('forward', true);
    await new Promise(r => setTimeout(r, 3000));
    bot.setControlState('forward', false);
    await new Promise(r => setTimeout(r, 15000));
    // Bring spectator along to the new dimension
    const dim = bot.game.dimension;
    const bp = bot.entity.position;
    bot.chat(`/execute in minecraft:${dim.replace('the_','')} run tp shriu2005 ${Math.floor(bp.x)} ${Math.floor(bp.y)} ${Math.floor(bp.z)}`);
    setTimeout(() => {
      bot.chat('/gamemode spectator shriu2005');
      bot.chat('/spectate SpeedrunBot shriu2005');
    }, 2000);
    return { success: true, dimension: dim };
  },

  async find_structure(name) {
    return new Promise(resolve => {
      const handler = msg => {
        const t = msg.toString();
        if (t.includes('[') || t.includes('nearest')) {
          bot.removeListener('messagestr', handler);
          const m = t.match(/\[(-?\d+),\s*~?,?\s*(-?\d+)\]/);
          resolve(m ? { success: true, x: +m[1], z: +m[2] } : { success: false, error: t });
        }
      };
      bot.on('messagestr', handler);
      bot.chat(`/locate structure ${name}`);
      setTimeout(() => { bot.removeListener('messagestr', handler); resolve({ success: false, error: 'timeout' }); }, 5000);
    });
  },

  async chat(message) {
    bot.chat(message);
    await new Promise(r => setTimeout(r, 500));
    return { success: true };
  },
};

// --- HTTP API ---
const server = http.createServer(async (req, res) => {
  if (req.method === 'POST' && req.url === '/action') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const { action, args } = JSON.parse(body);
        if (!ACTIONS[action]) { res.writeHead(400); res.end(JSON.stringify({ error: `Unknown: ${action}` })); return; }
        const result = await ACTIONS[action](...(args || []));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ result, state: getState() }));
      } catch (e) { if (!res.headersSent) { res.writeHead(500); res.end(JSON.stringify({ error: e.message })); } }
    });
  } else if (req.method === 'GET' && req.url === '/state') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(getState()));
  } else if (req.method === 'POST' && req.url === '/spectate') {
    bot.chat('/gamemode spectator shriu2005');
    bot.chat('/spectate SpeedrunBot shriu2005');
    res.writeHead(200); res.end(JSON.stringify({ spectate: true }));
  } else if (req.method === 'POST' && req.url === '/reset') {
    if (!bot.entity) { res.writeHead(503); res.end(JSON.stringify({ error: 'Bot not ready' })); return; }
    startTime = Date.now();
    objectivesCompleted = [];
    bot.chat('/clear');
    bot.chat('/effect give @s minecraft:instant_health 1 255');
    bot.chat('/effect give @s minecraft:saturation 1 255');
    bot.chat('/effect clear @s');
    bot.chat('/tp @s 26 63 82');
    bot.chat('/time set day');
    bot.chat('/weather clear');
    bot.chat('/difficulty easy');
    bot.chat('/gamerule keepInventory true');
    bot.chat('/gamerule sendCommandFeedback false');
    bot.chat('/gamemode survival @s');
    bot.chat('/tick rate 200');
    setTimeout(() => {
      bot.chat('/gamemode spectator shriu2005');
      bot.chat('/spectate SpeedrunBot shriu2005');
    }, 2000);
    res.writeHead(200); res.end(JSON.stringify({ reset: true }));
  } else { res.writeHead(404); res.end('Not found'); }
});


function createBot() {
  bot = mineflayer.createBot({ host: HOST, port: PORT, username: BOT_NAME, version: '1.20.4' });
  bot.loadPlugin(pathfinder.pathfinder);
  bot.once('spawn', () => {
    startTime = Date.now();
    console.log(`Bot spawned at (${bot.entity.position})`);
    // Viewer disabled — using Minecraft client instead
    bot.chat('/op shriu2005');
    bot.chat('/gamemode spectator shriu2005');
  });
  bot.on('death', () => console.log('Bot died!'));
  bot.on('spawn', () => {
    setTimeout(() => {
      bot.chat('/gamemode spectator shriu2005');
      bot.chat('/spectate SpeedrunBot shriu2005');
    }, 1000);
  });
  bot.on('playerJoined', (player) => {
    if (player.username === 'shriu2005') {
      setTimeout(() => {
        bot.chat('/gamemode spectator shriu2005');
        bot.chat('/spectate SpeedrunBot shriu2005');
      }, 2000);
    }
  });
  bot.on('error', e => console.error('Bot error:', e));
  bot.on('end', () => { console.log('Disconnected, reconnecting...'); setTimeout(createBot, 5000); });
}

createBot();
server.listen(API_PORT, () => console.log(`API on :${API_PORT}`));
