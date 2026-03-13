import { Queue } from "bullmq";
import { redisConnection } from "./connection.js";

export interface BacktestJobData {
  sessionId: string;
  strategyJson: string;
  instruments: string[];
  timeframes: string[];
  paramGrid?: Record<string, unknown>;
  dataDir?: string;
  engineDbPath?: string;
  optimizeMetric?: string;
  optimizer?: "grid" | "bayesian" | "genetic";
  nTrials?: number;
  populationSize?: number;  // NSGA-II population size (genetic optimizer only)
  fromDate?: string;  // e.g. "2022-01-01" — triggers auto-download if data missing
  toDate?: string;    // e.g. "2024-12-31" — defaults to yesterday
}

export type BacktestJobName = "backtest";

export const backtestQueue = new Queue<BacktestJobData, void, BacktestJobName>("backtest", {
  connection: redisConnection,
  defaultJobOptions: {
    attempts: 1,
    removeOnComplete: 100,
    removeOnFail: 50,
  },
});
