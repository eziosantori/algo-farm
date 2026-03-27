import { mkdirSync, writeFileSync } from "fs";
import { join, relative } from "path";
import type Database from "better-sqlite3";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import { CTraderAdapter } from "./ctrader.adapter.js";
import { PineAdapter } from "./pine.adapter.js";
import { generateOpsetJson } from "./opset.adapter.js";
import { StrategyRepository } from "../../db/repositories/strategy.repo.js";

export interface GeneratedFile {
  path: string;
  filename: string;
  format: string;
}

/**
 * Generates all export files for a strategy and writes them to disk.
 * Updates `strategies.export_dir` in the DB with the relative directory path.
 *
 * Files written (all inside `<baseDir>/<strategyName>_exports/`):
 *   - <name>.cs          — cTrader C# bot
 *   - <name>.pine        — TradingView Pine Script
 *   - <name>.cbotset     — default cBotSet (no per-pair override)
 *   - <name>_<INST>_<TF>.cbotset  — one per entry in param_overrides
 *
 * @param strategy    Parsed strategy definition
 * @param strategyId  DB id to update export_dir on
 * @param baseDir     Absolute path to parent directory (e.g. .../engine/strategies/validated)
 * @param db          better-sqlite3 Database instance
 */
export function saveExportFiles(
  strategy: StrategyDefinition,
  strategyId: string,
  baseDir: string,
  db: Database.Database,
): GeneratedFile[] {
  const exportDir = join(baseDir, `${strategy.name}_exports`);
  mkdirSync(exportDir, { recursive: true });

  const files: GeneratedFile[] = [];

  const write = (filename: string, content: string, format: string) => {
    const fullPath = join(exportDir, filename);
    writeFileSync(fullPath, content, "utf-8");
    files.push({ path: fullPath, filename, format });
  };

  // .cs — cTrader C# bot
  write(
    `${strategy.name}.cs`,
    new CTraderAdapter().generate(strategy),
    "ctrader",
  );

  // .pine — TradingView Pine Script
  write(
    `${strategy.name}.pine`,
    new PineAdapter().generate(strategy),
    "pine",
  );

  // .cbotset — default (no per-pair params)
  write(
    `${strategy.name}.cbotset`,
    generateOpsetJson(strategy),
    "opset",
  );

  // per-pair .cbotset files from param_overrides
  const overrides = (strategy as Record<string, unknown>)["param_overrides"] as
    | Record<string, Record<string, unknown>>
    | undefined;

  if (overrides) {
    for (const [instrument, tfMap] of Object.entries(overrides)) {
      if (!tfMap || typeof tfMap !== "object") continue;
      for (const timeframe of Object.keys(tfMap)) {
        write(
          `${strategy.name}_${instrument}_${timeframe}.cbotset`,
          generateOpsetJson(strategy, instrument, timeframe),
          "opset",
        );
      }
    }
  }

  // Record relative path in DB
  const relativeDir = relative(process.cwd(), exportDir);
  new StrategyRepository(db).updateExportDir(strategyId, relativeDir);

  return files;
}
