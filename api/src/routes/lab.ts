import { Router, Request, Response } from "express";
import { z } from "zod";
import { getDb } from "../db/client.js";
import { LabRepository } from "../db/repositories/lab.repo.js";
import { validateBody } from "../middleware/validate.js";

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
});

const AddResultSchema = z.object({
  instrument: z.string().min(1),
  timeframe: z.string().min(1),
  params_json: z.string().min(1),
  metrics_json: z.string().min(1),
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
  status: z.enum(["running", "completed"]),
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

export default router;
