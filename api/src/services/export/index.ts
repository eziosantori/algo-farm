import { CTraderAdapter } from "./ctrader.adapter.js";
import { PineAdapter } from "./pine.adapter.js";
import type { ExportAdapter } from "./types.js";

const ADAPTERS: Record<string, ExportAdapter> = {
  ctrader: new CTraderAdapter(),
  pine: new PineAdapter(),
};

export function getExportAdapter(format: string): ExportAdapter | undefined {
  return ADAPTERS[format];
}

export type { ExportAdapter } from "./types.js";
