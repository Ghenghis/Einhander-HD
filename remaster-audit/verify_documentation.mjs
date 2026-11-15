#!/usr/bin/env node
// Lightweight, read-only checks. No build, game, network or GPU work.
// Run: node remaster-audit/verify_documentation.mjs --output docs/media/gallery/documentation-verification-results.json
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--output')) {
  throw new Error('Usage: node remaster-audit/verify_documentation.mjs [--output relative-report.json]');
}
const output = args[1] ? path.resolve(root, args[1]) : null;
if (output && (path.relative(root, output).startsWith('..') || !output.endsWith('.json'))) {
  throw new Error('Output must be a JSON file inside this checkout');
}
const git = async (...argv) => (await run('git', argv, {
  cwd: root, timeout: 10000, maxBuffer: 8000000
})).stdout.trim();
const tracked = new Set((await git('ls-files')).split('\n'));
const objectFormat = await git('rev-parse', '--show-object-format');
const index = new Map((await git('ls-files', '-s', '-z')).split('\0').filter(Boolean).map(row => {
  const tab = row.indexOf('\t');
  return [row.slice(tab + 1), row.slice(0, tab).split(' ')[1]];
}));
const candidates = [...new Set((await git('ls-files', '--cached', '--others', '--exclude-standard',
  'README.md', 'CLAUDE.md', 'windows-x64/README.md', 'docs', 'coordination',
  'remaster-audit/REMASTER_COMPLETION_PLAN.md', 'remaster-audit/runtime-diagnostics-v58'
)).split('\n'))].filter(Boolean).sort();
const docs = candidates.filter(p => /\.(md|html)$/i.test(p));
const jsonFiles = candidates.filter(p => /\.json$/i.test(p) && path.resolve(root, p) !== output
  && p !== 'docs/media/gallery/documentation-verification-results.json');
const files = [], issues = [], external = new Set();
let localLinks = 0;
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const blobHash = bytes => crypto.createHash(objectFormat)
  .update('blob ' + bytes.length + '\0').update(bytes).digest('hex');

for (const file of [...docs, ...jsonFiles]) {
  const bytes = await fs.readFile(path.join(root, file));
  const text = bytes.toString('utf8');
  const normalized = Buffer.from(text.replace(/\r\n/g, '\n'), 'utf8');
  const oid = index.get(file);
  const indexedBytes = oid === blobHash(bytes) ? bytes
    : oid === blobHash(normalized) ? normalized : null;
  files.push({
    path: file, bytes: bytes.length, working_tree_sha256: sha256(bytes),
    git_index_blob: oid || null,
    git_index_sha256: indexedBytes ? sha256(indexedBytes) : null,
    git_index_bytes: indexedBytes ? indexedBytes.length : null
  });
  if (!tracked.has(file)) issues.push({ file, problem: 'document_not_in_git_index' });
  else if (!indexedBytes) issues.push({ file, problem: 'verified_document_differs_from_git_index' });
  if (jsonFiles.includes(file)) {
    try { JSON.parse(text); } catch (e) {
      issues.push({ file, problem: 'invalid_json', detail: e.message });
    }
    continue;
  }
  // Strip fenced examples. Fragments and remote destinations are outside this check.
  const body = text.replace(/\x60{3}[\s\S]*?\x60{3}|~~~[\s\S]*?~~~/g, '');
  const links = [...body.matchAll(/\]\(<?([^\s)>]+)>?(?:\s+"[^"]*")?\)|(?:href|src)=["']([^"']+)["']/g)];
  for (const match of links) {
    const url = match[1] || match[2];
    if (/^https?:/i.test(url)) { external.add(url); continue; }
    if (/^(#|mailto:|data:|javascript:|plugin:|app:)/i.test(url)) continue;
    let target = url.split(/[?#]/)[0];
    if (!target) continue;
    try { target = decodeURIComponent(target); } catch {
      issues.push({ file, url, problem: 'invalid_url_encoding' }); continue;
    }
    localLinks++;
    const absolute = path.resolve(root, path.dirname(file), target);
    const relative = path.relative(root, absolute).replaceAll('\\', '/');
    if (relative === '..' || relative.startsWith('../') || path.isAbsolute(relative)) {
      issues.push({ file, url, problem: 'link_outside_checkout' }); continue;
    }
    const stat = await fs.stat(absolute).catch(e => {
      if (e.code === 'ENOENT' || e.code === 'ENOTDIR') return null;
      throw e;
    });
    if (!stat) {
      issues.push({ file, url, target: relative, problem: 'missing_local_target' }); continue;
    }
    const included = stat.isDirectory()
      ? [...tracked].some(p => p.startsWith(relative.replace(/\/$/, '') + '/'))
      : tracked.has(relative);
    if (!included) issues.push({ file, url, target: relative, problem: 'target_not_in_git_index' });
  }
}
const report = {
  generated_at_utc: new Date().toISOString(),
  base_head_before_documentation_commit: await git('rev-parse', 'HEAD'),
  verifier: {
    path: 'remaster-audit/verify_documentation.mjs',
    sha256: sha256(await fs.readFile(fileURLToPath(import.meta.url)))
  },
  scope: {
    documents: 'Project/platform README, CLAUDE, authored docs Markdown/HTML, coordination Markdown, restoration plan and v58 diagnostic package',
    json: 'Public docs, coordination and v58 diagnostic package JSON, excluding this generated report',
    checks: ['local link existence', 'linked targets included in Git index', 'JSON syntax',
      'SHA256 snapshot of checked files and matching Git-index bytes, allowing verified CRLF-to-LF conversion'],
    limits: ['No external URL fetches', 'No fragment/anchor validation', 'No visual rendering check',
      'Link and syntax success do not prove semantic completeness or in-game acceptance',
      'Private runtime artifacts are documented separately; ROM, generated game data and user state stay local'],
    e2e_gameplay_acceptance: 'pending; no performance, audio, whole-stage or seven-stage completion claim'
  },
  document_count: docs.length,
  json_count: jsonFiles.length,
  local_links_checked: localLinks,
  external_urls_not_fetched: [...external].sort(),
  files: files.sort((a, b) => a.path.localeCompare(b.path)),
  issues,
  passed: issues.length === 0
};
const serialized = JSON.stringify(report, null, 2) + '\n';
if (output) {
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(output, serialized);
  console.log(JSON.stringify({
    passed: report.passed, document_count: docs.length, json_count: jsonFiles.length,
    local_links_checked: localLinks, issues, report: path.relative(root, output)
  }));
} else console.log(serialized);
if (!report.passed) process.exitCode = 1;
