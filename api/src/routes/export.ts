import { existsSync, readFileSync } from "fs";
import { join, resolve, basename, dirname } from "path";
import { fileURLToPath } from "url";
import { Router, Request, Response } from "express";
import { getDb } from "../db/client.js";
import { StrategyRepository } from "../db/repositories/strategy.repo.js";
import { getExportAdapter, generateOpsetXml } from "../services/export/index.js";
import { saveExportFiles } from "../services/export/file-generator.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// api/src/routes/ → ../../../ → monorepo root
const MONOREPO_ROOT = resolve(__dirname, "../../..");
const DEFAULT_VALIDATED_DIR = resolve(MONOREPO_ROOT, "engine/strategies/validated");

const router = Router();

function getRepo(): StrategyRepository {
  return new StrategyRepository(getDb());
}

// ---------------------------------------------------------------------------
// Helpers for disk-first serving
// ---------------------------------------------------------------------------

function diskPath(exportDir: string, filename: string): string {
  return join(resolve(process.cwd(), exportDir), filename);
}

// ---------------------------------------------------------------------------
// POST /strategies/:id/export/generate — pre-generate and save files to disk
// ---------------------------------------------------------------------------
router.post(
  "/:id/export/generate",
  (req: Request, res: Response): void => {
    const { id } = req.params as { id: string };

    const record = getRepo().get(id);
    if (!record) {
      res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
      return;
    }

    try {
      const baseDir = DEFAULT_VALIDATED_DIR;
      const files = saveExportFiles(record.definition, id, baseDir, getDb());

      // Re-fetch to get updated export_dir
      const updated = getRepo().get(id);

      res.json({
        success: true,
        export_dir: updated?.export_dir ?? null,
        files: files.map((f) => f.filename),
      });
    } catch (err) {
      res.status(500).json({ error: "EXPORT_FAILED", message: String(err) });
    }
  }
);

// ---------------------------------------------------------------------------
// GET /strategies/:id/export/:format/preview → { code, filename, source }
// ---------------------------------------------------------------------------
router.get(
  "/:id/export/:format/preview",
  (req: Request, res: Response): void => {
    const { id, format } = req.params as { id: string; format: string };

    const adapter = getExportAdapter(format);
    if (!adapter) {
      res.status(400).json({
        error: "UNSUPPORTED_FORMAT",
        message: `Format '${format}' is not supported. Use 'ctrader', 'pine', or 'opset'.`,
      });
      return;
    }

    const record = getRepo().get(id);
    if (!record) {
      res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
      return;
    }

    const name = record.definition.name;
    const instrument = req.query["instrument"] as string | undefined;
    const timeframe = req.query["timeframe"] as string | undefined;

    // Disk-first: opset with per-pair params
    if (format === "opset" && instrument && timeframe && record.export_dir) {
      const filename = `${name}_${instrument}_${timeframe}.cbotset`;
      const file = diskPath(record.export_dir, filename);
      if (existsSync(file)) {
        res.json({ code: readFileSync(file, "utf-8"), filename, source: "disk" });
        return;
      }
    }

    // Disk-first: ctrader and pine (and opset default)
    if (record.export_dir) {
      const suffix = format === "opset" && instrument && timeframe
        ? `_${instrument}_${timeframe}` : "";
      const filename = `${name}${suffix}.${adapter.fileExtension}`;
      const file = diskPath(record.export_dir, filename);
      if (existsSync(file)) {
        res.json({ code: readFileSync(file, "utf-8"), filename, source: "disk" });
        return;
      }
    }

    // Fallback: adapter generate
    let code: string;
    let filename: string;
    if (format === "opset") {
      code = generateOpsetXml(record.definition, instrument, timeframe);
      const suffix = instrument && timeframe ? `_${instrument}_${timeframe}` : "";
      filename = `${name}${suffix}.${adapter.fileExtension}`;
    } else {
      code = adapter.generate(record.definition);
      filename = `${name}.${adapter.fileExtension}`;
    }

    res.json({ code, filename, source: "adapter" });
  }
);

// ---------------------------------------------------------------------------
// GET /strategies/:id/export/:format → file download
// ---------------------------------------------------------------------------
router.get("/:id/export/:format", (req: Request, res: Response): void => {
  const { id, format } = req.params as { id: string; format: string };

  const adapter = getExportAdapter(format);
  if (!adapter) {
    res.status(400).json({
      error: "UNSUPPORTED_FORMAT",
      message: `Format '${format}' is not supported. Use 'ctrader', 'pine', or 'opset'.`,
    });
    return;
  }

  const record = getRepo().get(id);
  if (!record) {
    res.status(404).json({ error: "NOT_FOUND", message: "Strategy not found" });
    return;
  }

  const name = record.definition.name;
  const instrument = req.query["instrument"] as string | undefined;
  const timeframe = req.query["timeframe"] as string | undefined;

  const sendFile = (file: string, filename: string) => {
    res.setHeader("Content-Type", adapter.mimeType);
    res.setHeader("Content-Disposition", `attachment; filename="${basename(filename)}"`);
    res.send(readFileSync(file, "utf-8"));
  };

  // Disk-first: opset per-pair
  if (format === "opset" && instrument && timeframe && record.export_dir) {
    const filename = `${name}_${instrument}_${timeframe}.cbotset`;
    const file = diskPath(record.export_dir, filename);
    if (existsSync(file)) {
      sendFile(file, filename);
      return;
    }
  }

  // Disk-first: ctrader, pine, and opset default
  if (record.export_dir) {
    const suffix = format === "opset" && instrument && timeframe
      ? `_${instrument}_${timeframe}` : "";
    const filename = `${name}${suffix}.${adapter.fileExtension}`;
    const file = diskPath(record.export_dir, filename);
    if (existsSync(file)) {
      sendFile(file, filename);
      return;
    }
  }

  // Fallback: adapter generate
  let code: string;
  let filename: string;
  if (format === "opset") {
    code = generateOpsetXml(record.definition, instrument, timeframe);
    const suffix = instrument && timeframe ? `_${instrument}_${timeframe}` : "";
    filename = `${name}${suffix}.${adapter.fileExtension}`;
  } else {
    code = adapter.generate(record.definition);
    filename = `${name}.${adapter.fileExtension}`;
  }

  res.setHeader("Content-Type", adapter.mimeType);
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  res.send(code);
});

export default router;
