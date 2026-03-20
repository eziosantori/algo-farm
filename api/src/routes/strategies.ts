import { Router, Request, Response } from "express";
import { z } from "zod";
import { getDb } from "../db/client.js";
import { StrategyRepository } from "../db/repositories/strategy.repo.js";
import { validateBody } from "../middleware/validate.js";
import { StrategyDefinitionSchema } from "@algo-farm/shared/strategy";

const LifecycleStatusSchema = z.object({
  lifecycle_status: z.enum([
    "draft",
    "optimizing",
    "validated",
    "production_standard",
    "production_aggressive",
    "production_defensive",
  ]),
});

const router = Router();

function getRepo(): StrategyRepository {
  return new StrategyRepository(getDb());
}

function paramId(req: Request): string {
  return req.params["id"] as string;
}

router.post(
  "/strategies",
  validateBody(StrategyDefinitionSchema),
  (_req: Request, res: Response): void => {
    const repo = getRepo();
    const result = repo.create(_req.body);
    res.status(201).json(result);
  }
);

router.get("/strategies", (req: Request, res: Response): void => {
  const repo = getRepo();
  let strategies = repo.list();

  const statusFilter = req.query["lifecycle_status"] as string | undefined;
  if (statusFilter) {
    const allowed = new Set(statusFilter.split(",").map((s) => s.trim()));
    strategies = strategies.filter((s) => allowed.has(s.lifecycle_status));
  }

  res.json({ strategies });
});

router.get("/strategies/:id", (req: Request, res: Response): void => {
  const repo = getRepo();
  const record = repo.get(paramId(req));

  if (!record) {
    res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
    return;
  }

  res.json(record);
});

router.put(
  "/strategies/:id",
  validateBody(StrategyDefinitionSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();
    const updated = repo.update(paramId(req), req.body);

    if (!updated) {
      res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
      return;
    }

    res.json({ success: true });
  }
);

router.patch(
  "/strategies/:id/lifecycle",
  validateBody(LifecycleStatusSchema),
  (req: Request, res: Response): void => {
    const repo = getRepo();
    const updated = repo.updateLifecycleStatus(paramId(req), req.body.lifecycle_status);
    if (!updated) {
      res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
      return;
    }
    res.json({ success: true });
  }
);

router.delete("/strategies/:id", (req: Request, res: Response): void => {
  const repo = getRepo();
  const deleted = repo.delete(paramId(req));

  if (!deleted) {
    res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
    return;
  }

  res.status(204).send();
});

export default router;
