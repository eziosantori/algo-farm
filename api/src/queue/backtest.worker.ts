import { Worker, type Job } from "bullmq";
import { spawn } from "child_process";
import { mkdtempSync, writeFileSync, rmSync, existsSync } from "fs";
import { join, resolve, dirname } from "path";
import { tmpdir } from "os";
import { fileURLToPath } from "url";
import { redisConnection } from "./connection.js";
import type { BacktestJobData, BacktestJobName } from "./backtest.queue.js";
import { getDb } from "../db/client.js";
import { LabRepository } from "../db/repositories/lab.repo.js";
import { broadcast } from "../websocket/server.js";

// Project root = two levels up from api/src/queue/
const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

const PYTHON_BIN = process.env.PYTHON_BIN ?? join(PROJECT_ROOT, "engine/.venv/bin/python");
const DATA_DIR = process.env.DATA_DIR ?? join(PROJECT_ROOT, "engine/data");
const ENGINE_DB_PATH = process.env.ENGINE_DB_PATH ?? join(PROJECT_ROOT, "engine_runs.db");

function yesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function dataFileExists(dataDir: string, instrument: string, timeframe: string): boolean {
  return existsSync(join(dataDir, instrument, `${timeframe}.parquet`));
}

async function downloadData(
  instruments: string[],
  timeframes: string[],
  dataDir: string,
  fromDate: string,
  toDate: string,
  sessionId: string
): Promise<void> {
  const missing = instruments.filter((inst) =>
    timeframes.some((tf) => !dataFileExists(dataDir, inst, tf))
  );
  if (missing.length === 0) return;

  console.log(`[worker] Downloading data for: ${missing.join(",")} / ${timeframes.join(",")}`);
  broadcast(sessionId, { type: "downloading", sessionId, instruments: missing, timeframes, fromDate, toDate });

  await new Promise<void>((resolve, reject) => {
    const proc = spawn(
      PYTHON_BIN,
      [
        join(PROJECT_ROOT, "engine/download.py"),
        "--instruments", missing.join(","),
        "--timeframes", timeframes.join(","),
        "--from", fromDate,
        "--to", toDate,
        "--data-dir", dataDir,
      ],
      { cwd: PROJECT_ROOT, stdio: ["ignore", "pipe", "pipe"] }
    );

    proc.stdout.on("data", (chunk: Buffer) => process.stdout.write(chunk));
    proc.stderr.on("data", (chunk: Buffer) => process.stderr.write(chunk));

    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`download.py exited with code ${code}`));
    });
    proc.on("error", reject);
  });
}

async function processBacktestJob(job: Job<BacktestJobData>): Promise<void> {
  const {
    sessionId,
    strategyJson,
    instruments,
    timeframes,
    paramGrid,
    dataDir = DATA_DIR,
    engineDbPath = ENGINE_DB_PATH,
    optimizeMetric = "sharpe_ratio",
    optimizer = "grid",
    nTrials = 50,
    populationSize = 20,
    fromDate = "2024-01-01",
    toDate = yesterday(),
  } = job.data;

  const db = getDb();
  const repo = new LabRepository(db);

  repo.updateSessionStatus(sessionId, "running");
  broadcast(sessionId, { type: "started", sessionId });

  // Auto-download missing data before running the backtest (async — does not block event loop)
  try {
    await downloadData(instruments, timeframes, dataDir, fromDate, toDate, sessionId);
  } catch (err) {
    console.error("[worker] Data download failed:", err);
    broadcast(sessionId, { type: "download_failed", sessionId, error: String(err) });
    // Continue anyway — engine will log DataNotFound per instrument
  }

  const tmpDir = mkdtempSync(join(tmpdir(), "algo-farm-"));
  const strategyPath = join(tmpDir, "strategy.json");
  writeFileSync(strategyPath, strategyJson);

  const args = [
    join(PROJECT_ROOT, "engine/run.py"),
    "--strategy", strategyPath,
    "--instruments", instruments.join(","),
    "--timeframes", timeframes.join(","),
    "--db", engineDbPath,
    "--data-dir", dataDir,
    "--metric", optimizeMetric,
    "--optimize", optimizer,
  ];

  if (optimizer === "bayesian" || optimizer === "genetic") {
    args.push("--n-trials", String(nTrials));
  }
  if (optimizer === "genetic") {
    args.push("--population-size", String(populationSize));
  }

  if (paramGrid && Object.keys(paramGrid).length > 0) {
    const gridPath = join(tmpDir, "param_grid.json");
    writeFileSync(gridPath, JSON.stringify(paramGrid));
    args.push("--param-grid", gridPath);
  }

  try {
    await new Promise<void>((resolve, reject) => {
      const proc = spawn(PYTHON_BIN, args, {
        stdio: ["ignore", "pipe", "pipe"],
        cwd: PROJECT_ROOT,
      });

      let buffer = "";

      proc.stdout.on("data", (chunk: Buffer) => {
        buffer += chunk.toString();
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg = JSON.parse(line) as Record<string, unknown>;
            handleEngineMessage(msg, sessionId, repo);
            broadcast(sessionId, { ...msg, sessionId });
          } catch {
            // ignore JSON parse errors on malformed lines
          }
        }
      });

      proc.stderr.on("data", (chunk: Buffer) => {
        process.stderr.write(chunk);
      });

      proc.on("close", (code) => {
        try { rmSync(tmpDir, { recursive: true }); } catch { /* ignore */ }

        if (code === 0 || code === 2) {
          repo.updateSessionStatus(sessionId, "completed");
          broadcast(sessionId, { type: "session_completed", sessionId });
          resolve();
        } else {
          repo.updateSessionStatus(sessionId, "failed");
          broadcast(sessionId, { type: "session_failed", sessionId, exitCode: code });
          reject(new Error(`Engine process exited with code ${code}`));
        }
      });

      proc.on("error", (err) => {
        try { rmSync(tmpDir, { recursive: true }); } catch { /* ignore */ }
        repo.updateSessionStatus(sessionId, "failed");
        reject(err);
      });
    });
  } catch (err) {
    throw err;
  }
}

function handleEngineMessage(
  msg: Record<string, unknown>,
  sessionId: string,
  repo: LabRepository
): void {
  if (msg["type"] === "result") {
    const instrument = msg["instrument"] as string;
    const timeframe = msg["timeframe"] as string;
    const params = (msg["params"] as Record<string, unknown>) ?? {};
    const metrics = (msg["metrics"] as Record<string, unknown>) ?? {};

    try {
      repo.addResult({
        session_id: sessionId,
        instrument,
        timeframe,
        params_json: JSON.stringify(params),
        metrics_json: JSON.stringify(metrics),
      });
    } catch (err) {
      console.error("[worker] Failed to persist result:", err);
    }
  }
}

let workerInstance: Worker<BacktestJobData, void, BacktestJobName> | null = null;

export function startWorker(): void {
  const concurrency = parseInt(process.env.WORKER_CONCURRENCY ?? "2", 10);

  workerInstance = new Worker<BacktestJobData, void, BacktestJobName>("backtest", processBacktestJob, {
    connection: redisConnection,
    concurrency,
    lockDuration: 15 * 60 * 1000,   // 15 min — covers long downloads + backtest runs
    lockRenewTime: 3 * 60 * 1000,   // renew every 3 min
  });

  workerInstance.on("failed", (job, err) => {
    console.error(`[worker] Job ${job?.id} failed:`, err.message);
  });

  workerInstance.on("completed", (job) => {
    console.log(`[worker] Job ${job.id} completed`);
  });

  console.log(`[worker] Backtest worker started (concurrency=${concurrency})`);
}

export async function stopWorker(): Promise<void> {
  if (workerInstance) {
    await workerInstance.close();
    workerInstance = null;
  }
}
