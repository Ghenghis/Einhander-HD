// Stdio MCP connector scoped to canonical Einhander coordination. No game launch.
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {runtime, workspaceRoot} from './workspace-runtime.mjs';
import {connect} from './hermes-client.mjs';
import {authorize, exposedTools} from './devin-observer-policy.mjs';

const {release} = await runtime();
const sdk = path.join(release, 'node_modules/@modelcontextprotocol/sdk/dist/esm');
const {Server} = await import(pathToFileURL(path.join(sdk, 'server/index.js')).href);
const {StdioServerTransport} = await import(pathToFileURL(path.join(sdk, 'server/stdio.js')).href);
const {ListToolsRequestSchema, CallToolRequestSchema} = await import(pathToFileURL(path.join(sdk, 'types.js')).href);
const upstream = await connect();
const catalog = (await upstream.client.listTools()).tools.filter(x => exposedTools.has(x.name));
if (!catalog.some(x => x.name === 'hermes_get_workspace') || !catalog.some(x => x.name === 'hermes_send_message')) {
  await upstream.close();
  throw new Error('Managed Hermes tool catalog lacks onboarding requirements');
}
const names = new Set(catalog.map(x => x.name));
const server = new Server({name:'einhander-devin-observer', version:'1.0.0'}, {
  capabilities:{tools:{}},
  instructions:`Canonical workspace: ${workspaceRoot}. Read coordination/DEVIN-HANDOFF.md before work. This connector permits observation and identity-bound coordination only; it does not grant edit or runtime authority. A connected server is not proof of an active model.`,
});
server.setRequestHandler(ListToolsRequestSchema, async () => ({tools:catalog}));
server.setRequestHandler(CallToolRequestSchema, async request => {
  try {
    if (!names.has(request.params.name)) throw new Error('Tool is not exposed');
    const args = authorize(request.params.name, request.params.arguments);
    const result = await upstream.call(request.params.name, args);
    return {content:[{type:'text', text:JSON.stringify(result)}]};
  } catch (error) {
    return {isError:true, content:[{type:'text', text:String(error.message || error)}]};
  }
});
server.onclose = () => { void upstream.close(); };
await server.connect(new StdioServerTransport());
