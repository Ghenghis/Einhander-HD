@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0CLAUDE.md" exit /b 1
if not exist "%~dp0coordination\CLAUDE-HANDOFF.md" exit /b 1
claude --strict-mcp-config --mcp-config "%~dp0.mcp.json" "Read CLAUDE.md and coordination/CLAUDE-HANDOFF.md. Work autonomously in this Einhander workspace until the authorized project is complete. Join HermesProof as claude-einhander, read and act on your inbox, acknowledge quietly, and claim eligible work before coding. Continue after component handoffs. Before any waiting turn record a real checkpoint and armed monitor/next wake; a background mail watcher is not an active model. Honour explicit user stop/pause and platform limits. Report results with evidence to codex-einhander and then take the next task."
endlocal
