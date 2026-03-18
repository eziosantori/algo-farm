import { Router, Request, Response } from "express";
import { z } from "zod";
import { getDb } from "../db/client.js";
import { LabRepository } from "../db/repositories/lab.repo.js";
import { validateBody } from "../middleware/validate.js";
import { backtestQueue } from "../queue/backtest.queue.js";

const router = Router();

function getRepo(): LabRepository {
  return new LabRepository(getDb());
}

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const CreateSessionSchema = z.object({
  strategy_name: z.string().min(1),
  strategy_json: z.string().min(1),
  instruments: z.array(z.string().min(1)).min(1),
  timeframes: z.array(z.string().min(1)).min(1),
  constraints: z.record(z.number()).nullable().optional(),
  strategy_id: z.string().uuid().optional(),
  is_start: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional(),
  is_end:   z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional(),
});

const AddResultSchema = z.object({
  instrument: z.string().min(1),
  timeframe: z.string().min(1),
  params_json: z.string().min(1),
  metrics_json: z.string().min(1),
  split: z.enum(["is", "oos", "full"]).optional(),
});

const UpdateResultStatusSchema = z.object({
  status: z.enum([
    "pending",
    "validated",
    "rejected",
    "production_standard",
    "production_aggressive",
    "production_defensive",
  ]),
});

const UpdateSessionStatusSchema = z.object({
  status: z.enum(["running", "completed", "failed"]),
});

const RunSessionSchema = z.object({
  data_dir: z.string().optional(),
  engine_db_path: z.string().optional(),
  param_grid: z.record(z.unknown()).optional(),
  optimize_metric: z.string().optional(),
  optimizer: z.enum(["grid", "bayesian", "genetic"]).optional(),
  n_trials: z.number().int().positive().optional(),
  population_size: z.number().int().min(4).max(200).optional(),
  from_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  to_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  // IS window override (defaults handled in worker: 2022-01-01 → 2023-12-31)
  is_start: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  is_end:   z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
});

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

// POST /lab/sessions — create a new lab session
router.post(
  "/lab/sessions",
  validateBody(CreateSessionSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();
    const result = repo.createSession(req.body);
    res.status(201).json(result);
  }
);

// GET /lab/sessions — list all sessions (summary)
router.get("/lab/sessions", (_req: Request, res: Response): void => {
  const repo = getRepo();
  res.json({ sessions: repo.listSessions() });
});

// GET /lab/sessions/:id — session detail with all results
router.get("/lab/sessions/:id", (req: Request, res: Response): void => {
  const repo = getRepo();
  const session = repo.getSession(req.params["id"] as string);

  if (!session) {
    res.status(404).json({ error: "NOT_FOUND", message: "Session not found" });
    return;
  }

  res.json(session);
});

// PATCH /lab/sessions/:id/status — mark session completed / running
router.patch(
  "/lab/sessions/:id/status",
  validateBody(UpdateSessionStatusSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();
    const updated = repo.updateSessionStatus(
      req.params["id"] as string,
      req.body.status
    );

    if (!updated) {
      res.status(404).json({ error: "NOT_FOUND", message: "Session not found" });
      return;
    }

    res.json({ success: true });
  }
);

// POST /lab/sessions/:id/results — add a backtest result to a session
router.post(
  "/lab/sessions/:id/results",
  validateBody(AddResultSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();

    // Verify session exists
    if (!repo.getSession(req.params["id"] as string)) {
      res.status(404).json({ error: "NOT_FOUND", message: "Session not found" });
      return;
    }

    const result = repo.addResult({
      session_id: req.params["id"] as string,
      ...req.body,
    });

    res.status(201).json(result);
  }
);

// PATCH /lab/results/:id/status — validate / reject / promote to production
router.patch(
  "/lab/results/:id/status",
  validateBody(UpdateResultStatusSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();
    const updated = repo.updateResultStatus(
      req.params["id"] as string,
      req.body.status
    );

    if (!updated) {
      res.status(404).json({ error: "NOT_FOUND", message: "Result not found" });
      return;
    }

    res.json(updated);
  }
);

// POST /lab/sessions/:id/run — enqueue a session for async execution
router.post(
  "/lab/sessions/:id/run",
  validateBody(RunSessionSchema),
  async (req: Request, res: Response): Promise<void> => {
    const repo = getRepo();
    const session = repo.getSession(req.params["id"] as string);

    if (!session) {
      res.status(404).json({ error: "NOT_FOUND", message: "Session not found" });
      return;
    }

    try {
      const jobData = {
        sessionId: session.id,
        strategyJson: JSON.stringify(session.strategy),
        instruments: session.instruments,
        timeframes: session.timeframes,
        paramGrid: req.body.param_grid as Record<string, unknown> | undefined,
        dataDir: req.body.data_dir as string | undefined,
        engineDbPath: req.body.engine_db_path as string | undefined,
        optimizeMetric: req.body.optimize_metric as string | undefined,
        optimizer: req.body.optimizer as "grid" | "bayesian" | "genetic" | undefined,
        nTrials: req.body.n_trials as number | undefined,
        populationSize: req.body.population_size as number | undefined,
        fromDate: req.body.from_date as string | undefined,
        toDate: req.body.to_date as string | undefined,
        isStart: (req.body.is_start ?? session.is_start) as string | undefined,
        isEnd:   (req.body.is_end   ?? session.is_end)   as string | undefined,
      };

      const job = await backtestQueue.add("backtest" as const, jobData);
      res.status(202).json({ job_id: job.id, session_id: session.id });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Queue error";
      res.status(500).json({ error: "QUEUE_ERROR", message });
    }
  }
);

export default router;
