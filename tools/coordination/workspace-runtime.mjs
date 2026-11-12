import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const workspaceRoot = await fs.realpath(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..'));

export async function runtime() {
  // The existing managed installation supplies code; all mutable project state stays here.
  const managedRoot = path.join(os.homedir(), '.hermesproof-managed');
  const launcher = path.join(managedRoot, 'control/scripts/hermesproof-launch.mjs');
  const { resolveManagedServer } = await import(pathToFileURL(launcher).href);
  const server = await resolveManagedServer({ managedRoot, server: 'hermes3d-locks' });
  const release = path.dirname(path.dirname(server));
  return { managedRoot, launcher, release };
}

export function workspaceEnvironment(managedRoot) {
  return {
    ...process.env,
    HERMESPROOF_MANAGED_ROOT: managedRoot,
    MCP_LOCK_WORKSPACE: workspaceRoot,
    HERMES3D_WORKSPACE: workspaceRoot,
    HERMES_WORKSPACE_ROOT: workspaceRoot,
    MCP_LOCK_STATE_DIR: '.hermes3d_orchestrator',
  };
}
