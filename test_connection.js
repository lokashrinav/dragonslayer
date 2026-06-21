const http = require('http');

console.log('Testing bot API connection...');

http.get('http://localhost:3001/actions', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log('Bot API is running!');
    console.log('Available actions:', JSON.parse(data).actions);

    http.get('http://localhost:3001/state', (res2) => {
      let data2 = '';
      res2.on('data', chunk => data2 += chunk);
      res2.on('end', () => {
        const state = JSON.parse(data2);
        console.log('\nBot state:');
        console.log(`  Position: ${JSON.stringify(state.position)}`);
        console.log(`  Health: ${state.health}`);
        console.log(`  Dimension: ${state.dimension}`);
        console.log(`  Inventory items: ${state.inventory.length}`);
        console.log(`  Nearby blocks: ${Object.keys(state.nearby_blocks).length} types`);
        console.log('\nEverything works! Run agent.py to start the speedrun.');
      });
    });
  });
}).on('error', () => {
  console.log('Bot API not running. Start bot.js first with a Minecraft server running.');
});
