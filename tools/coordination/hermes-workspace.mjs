import { pathToFileURL } from 'node:url';
import { runtime, workspaceRoot, workspaceEnvironment } from './workspace-runtime.mjs';

const server = process.argv[2] || 'hermes3d-locks';
if (!['hermes3d-locks', 'hp-mha-serena'].includes(server)) throw new Error('Unknown project server');
if (process.argv.length > 3) throw new Error('Unexpected launcher arguments');
const { managedRoot, launcher } = await runtime();
const { launchManagedServer } = await import(pathToFileURL(launcher).href);
process.chdir(workspaceRoot);
process.exitCode = await launchManagedServer({ argv: ['--server', server], environment: workspaceEnvironment(managedRoot) });
