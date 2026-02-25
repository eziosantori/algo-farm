import { Router, Request, Response } from "express";
import { getDb } from "../db/client.js";
import { StrategyRepository } from "../db/repositories/strategy.repo.js";
import { validateBody } from "../middleware/validate.js";
import { StrategyDefinitionSchema } from "@algo-farm/shared/strategy";

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

router.get("/strategies", (_req: Request, res: Response): void => {
  const repo = getRepo();
  const strategies = repo.list();
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
