import { CTraderAdapter } from "./ctrader.adapter.js";
import { PineAdapter } from "./pine.adapter.js";
import { OpsetAdapter } from "./opset.adapter.js";
import type { ExportAdapter } from "./types.js";

const ADAPTERS: Record<string, ExportAdapter> = {
  ctrader: new CTraderAdapter(),
  pine: new PineAdapter(),
  opset: new OpsetAdapter(),
};

export function getExportAdapter(format: string): ExportAdapter | undefined {
  return ADAPTERS[format];
}

export type { ExportAdapter } from "./types.js";
export { generateOpsetXml } from "./opset.adapter.js";
