// Initial Devin connector: project observation and identity-bound messaging only.
export const owner = 'devin-einhander';
export const readTools = new Set([
  'hermes_get_workspace', 'hermes_list_presence', 'hermes_get_agent_profile',
  'hermes_list_agent_profiles', 'hermes_list_pending_tasks',
]);
export const ownTools = new Set([
  'hermes_get_inbox', 'hermes_wait_for_inbox', 'hermes_ack_message',
  'hermes_update_presence', 'hermes_heartbeat',
]);
export const exposedTools = new Set([...readTools, ...ownTools, 'hermes_send_message']);

export function authorize(name, input = {}) {
  if (!exposedTools.has(name)) throw new Error('Observer connector does not expose editing, locks, execution, workspace switching, or publication');
  if (input === null || typeof input !== 'object' || Array.isArray(input)) throw new Error('Tool arguments must be an object');
  const args = {...input};
  if (ownTools.has(name) && args.owner !== owner) throw new Error(`Use owner ${owner}; another actor cannot be impersonated`);
  if (name === 'hermes_send_message') {
    if (args.sender !== owner) throw new Error(`Use sender ${owner}`);
    if (!Array.isArray(args.recipients) || !args.recipients.length ||
        args.recipients.some(x => !['codex-einhander', 'claude-einhander'].includes(x))) {
      throw new Error('Onboarding messages may target only Codex and Claude in this project');
    }
  }
  if (name === 'hermes_wait_for_inbox') {
    args.timeoutMs = Math.min(40000, Math.max(1000, Number(args.timeoutMs) || 40000));
  }
  if (name === 'hermes_update_presence') {
    args.ttlSeconds = Math.min(900, Math.max(60, Number(args.ttlSeconds) || 300));
    args.role = 'read-only synchronization and review';
    if (!['working', 'waiting', 'reviewing', 'idle'].includes(args.status)) throw new Error('Use an honest onboarding presence state');
  }
  return args;
}
