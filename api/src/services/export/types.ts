import type { StrategyDefinition } from "@algo-farm/shared/strategy";

export interface ExportAdapter {
  format: "ctrader" | "pine";
  fileExtension: string;
  mimeType: string;
  generate(strategy: StrategyDefinition): string;
}
