/**
 * ENFORX — OpenClaw Plugin
 *
 * Registers the `enforx_trade` and `enforx_health` tools into OpenClaw.
 * When OpenClaw's agent detects trade intent in any message (Telegram, Slack,
 * Discord, etc.) it calls enforx_trade, which shells out to the Python
 * pipeline and returns the full 10-layer enforcement result.
 *
 * Install (from project root):
 *   openclaw plugins install --link ./plugin
 *
 * After install, from Telegram / any connected chat:
 *   "Buy 5 shares of AAPL"  →  OpenClaw calls enforx_trade automatically
 *   "Is the trading system ready?"  →  OpenClaw calls enforx_health
 */

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const execFileAsync = promisify(execFile);

// ENFORX project root — one level up from plugin/
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..");
const CORE_DIR = resolve(__dirname, "..", "core");

// ── Helpers ──────────────────────────────────────────────────────────────────

function resolvePython(config) {
  if (config?.pythonPath && existsSync(config.pythonPath)) return config.pythonPath;
  const venvPython = resolve(PROJECT_ROOT, "venv", "bin", "python3");
  if (existsSync(venvPython)) return venvPython;
  return "python3";
}

function resolveEnforxDir(config) {
  return config?.enforxDir || CORE_DIR;
}

async function runPipeline(command, config) {
  const python = resolvePython(config);
  const enforxDir = resolveEnforxDir(config);
  const timeoutMs = config?.timeoutMs ?? 120_000;

  const { stdout, stderr } = await execFileAsync(
    python,
    ["-m", "src.cli", command],
    { cwd: enforxDir, timeout: timeoutMs, env: { ...process.env } }
  );

  if (stderr?.trim()) {
    const realErrors = stderr
      .split("\n")
      .filter((l) => l.trim() && !l.includes("NotOpenSSLWarning") && !l.includes("urllib3"))
      .join("\n");
    if (realErrors) console.warn("[enforx]", realErrors);
  }

  return stdout.trim();
}

function summariseResult(raw) {
  const resultLine = raw.split("\n").findLast((l) => l.trim().startsWith("Result:"));
  if (resultLine) return resultLine.trim();
  if (raw.includes("PIPELINE SUCCESS")) return "Result: ✅ TRADE EXECUTED";
  if (raw.includes("BLOCKED")) return "Result: 🚫 BLOCKED by enforcement pipeline";
  return "Result: pipeline completed";
}

function pipelineError(err) {
  const msg = err?.message ?? String(err);
  if (err?.code === "ETIMEDOUT" || msg.includes("timed out"))
    return { error: "ENFORX pipeline timed out — deliberation agents may be slow. Try again." };
  if (msg.includes("ConnectionError") || msg.includes("OpenClaw"))
    return { error: "OpenClaw gateway unreachable. Run: openclaw gateway start" };
  return { error: `ENFORX pipeline error: ${msg}` };
}

// ── Plugin registration — OpenClaw calls this on gateway startup ─────────────

export default function register(api) {
  const config = api.getConfig?.() ?? {};

  console.log(
    `[enforx] Registering | python=${resolvePython(config)} | dir=${resolveEnforxDir(config)}`
  );

  // ── Tool: enforx_trade ──────────────────────────────────────────────────
  api.registerTool((toolCtx) => ({
    name: "enforx_trade",
    description:
      "Run a trade command through the ENFORX 10-layer Causal Integrity Enforcement pipeline. " +
      "Use this for ANY trade-related request: buy orders, sell orders, or anything involving " +
      "financial execution. The pipeline runs multi-agent deliberation (Analyst + Risk + Compliance), " +
      "enforces policy deterministically, and executes via Alpaca paper trading if all layers pass. " +
      "Returns a layer-by-layer result.",
    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description:
            "The natural language trade command. " +
            "Examples: 'Buy 5 shares of AAPL', 'Sell 3 MSFT at limit', 'Buy 100 TSLA'",
        },
      },
      required: ["command"],
    },
    handler: async ({ command }) => {
      if (!command?.trim()) return { error: "No command provided." };
      try {
        const raw = await runPipeline(command.trim(), toolCtx.config ?? config);
        return { summary: summariseResult(raw), details: raw };
      } catch (err) {
        return pipelineError(err);
      }
    },
  }));

  // ── Tool: enforx_health ─────────────────────────────────────────────────
  api.registerTool((toolCtx) => ({
    name: "enforx_health",
    description:
      "Check ENFORX system health — verifies the OpenClaw gateway, Alpaca paper trading " +
      "connection, and policy file. Use when the user asks if the trading system is ready.",
    parameters: { type: "object", properties: {}, required: [] },
    handler: async () => {
      try {
        const cfg = toolCtx.config ?? config;
        const { stdout } = await execFileAsync(
          resolvePython(cfg),
          ["-m", "src.cli", "--health"],
          { cwd: resolveEnforxDir(cfg), timeout: 15_000, env: { ...process.env } }
        );
        return { health: stdout.trim() };
      } catch (err) {
        return { error: `Health check failed: ${err?.message ?? err}` };
      }
    },
  }));
}
