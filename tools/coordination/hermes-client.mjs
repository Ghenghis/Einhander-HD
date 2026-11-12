import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { runtime, workspaceRoot, workspaceEnvironment } from './workspace-runtime.mjs';

export async function connect() {
  const { release, managedRoot } = await runtime();
  const sdk = path.join(release, 'node_modules/@modelcontextprotocol/sdk/dist/esm/client');
  const { Client } = await import(pathToFileURL(path.join(sdk, 'index.js')).href);
  const { StdioClientTransport } = await import(pathToFileURL(path.join(sdk, 'stdio.js')).href);
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.join(workspaceRoot, 'tools/coordination/hermes-workspace.mjs')],
    cwd: workspaceRoot,
    env: workspaceEnvironment(managedRoot),
    stderr: 'pipe',
  });
  transport.stderr?.on('data', () => {});
  const client = new Client({ name: 'einhander-workspace-coordination', version: '1.0.0' });
  try {
    await client.connect(transport);
    const call = async (name, args = {}) => {
      // This helper cannot switch to another project or request an outside cwd.
      if (['hermes_set_workspace', 'hermes_connect_project'].includes(name)) throw new Error('Workspace switching is disabled in this project client');
      for (const key of ['workspaceRoot', 'defaultWorkspaceRoot', 'cwd']) {
        if (args[key] && path.resolve(workspaceRoot, args[key]).toLowerCase() !== workspaceRoot.toLowerCase()) throw new Error(`${key} must be this workspace`);
      }
      const response = await client.callTool({ name, arguments: args }, undefined, { timeout: 45000 });
      const blocks = (response.content || []).filter(item => item.type === 'text').map(item => item.text);
      let result;
      try { result = JSON.parse(blocks.join('\n')); } catch { result = { text: blocks.join('\n') }; }
      if (response.isError || result.ok === false) throw new Error(`${name}: ${JSON.stringify(result)}`);
      return result;
    };
    const scope = await call('hermes_get_workspace');
    if (path.resolve(scope.workspace_root).toLowerCase() !== workspaceRoot.toLowerCase()) throw new Error('HermesProof workspace mismatch');
    return { client, call, close: () => client.close() };
  } catch (error) {
    await client.close().catch(() => {});
    throw error;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command = 'status', argument] = process.argv.slice(2);
  const session = await connect();
  try {
    let result;
    if (command === 'status') result = { workspace: await session.call('hermes_get_workspace'), presence: await session.call('hermes_list_presence'), queue: await session.call('hermes_list_pending_tasks') };
    else if (command === 'inbox') result = await session.call('hermes_get_inbox', { owner: argument || 'claude-einhander', includeAcked: false });
    else if (command === 'tools') result = (await session.client.listTools()).tools.map(({ name, inputSchema }) => ({ name, inputSchema }));
    else if (command === 'call-file') {
      if (!argument) throw new Error('Usage: hermes-client.mjs call-file <workspace-relative request.json>');
      const requestPath = await fs.realpath(path.resolve(workspaceRoot, argument));
      const relative = path.relative(workspaceRoot, requestPath);
      if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Request must be inside this workspace');
      const request = JSON.parse(await fs.readFile(requestPath, 'utf8'));
      result = await session.call(request.name, request.arguments || {});
    } else throw new Error('Commands: status, inbox [owner], tools, call-file <request.json>');
    console.log(JSON.stringify(result, null, 2));
  } finally { await session.close(); }
}
