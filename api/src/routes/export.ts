import { Router, Request, Response } from "express";
import { getDb } from "../db/client.js";
import { StrategyRepository } from "../db/repositories/strategy.repo.js";
import { getExportAdapter, generateOpsetXml } from "../services/export/index.js";

const router = Router();

function getRepo(): StrategyRepository {
  return new StrategyRepository(getDb());
}

// GET /strategies/:id/export/:format/preview → { code, filename }
router.get(
  "/:id/export/:format/preview",
  (req: Request, res: Response): void => {
    const { id, format } = req.params as { id: string; format: string };

    const adapter = getExportAdapter(format);
    if (!adapter) {
      res
        .status(400)
        .json({ error: "UNSUPPORTED_FORMAT", message: `Format '${format}' is not supported. Use 'ctrader', 'pine', or 'opset'.` });
      return;
    }

    const record = getRepo().get(id);
    if (!record) {
      res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
      return;
    }

    // For opset, support per-pair generation via query params
    let code: string;
    let filename: string;
    if (format === "opset") {
      const instrument = req.query["instrument"] as string | undefined;
      const timeframe = req.query["timeframe"] as string | undefined;
      code = generateOpsetXml(record.definition, instrument, timeframe);
      const suffix = instrument && timeframe ? `_${instrument}_${timeframe}` : "";
      filename = `${record.definition.name}${suffix}.${adapter.fileExtension}`;
    } else {
      code = adapter.generate(record.definition);
      filename = `${record.definition.name}.${adapter.fileExtension}`;
    }

    res.json({ code, filename });
  }
);

// GET /strategies/:id/export/:format → file download
router.get("/:id/export/:format", (req: Request, res: Response): void => {
  const { id, format } = req.params as { id: string; format: string };

  const adapter = getExportAdapter(format);
  if (!adapter) {
    res
      .status(400)
      .json({ error: "UNSUPPORTED_FORMAT", message: `Format '${format}' is not supported. Use 'ctrader', 'pine', or 'opset'.` });
    return;
  }

  const record = getRepo().get(id);
  if (!record) {
    res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
    return;
  }

  // For opset, support per-pair generation via query params
  let code: string;
  let filename: string;
  if (format === "opset") {
    const instrument = req.query["instrument"] as string | undefined;
    const timeframe = req.query["timeframe"] as string | undefined;
    code = generateOpsetXml(record.definition, instrument, timeframe);
    const suffix = instrument && timeframe ? `_${instrument}_${timeframe}` : "";
    filename = `${record.definition.name}${suffix}.${adapter.fileExtension}`;
  } else {
    code = adapter.generate(record.definition);
    filename = `${record.definition.name}.${adapter.fileExtension}`;
  }

  res.setHeader("Content-Type", adapter.mimeType);
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  res.send(code);
});

export default router;
