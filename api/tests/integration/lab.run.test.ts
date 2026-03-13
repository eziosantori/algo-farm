import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import request from "supertest";
import type { Application } from "express";

// Mock BullMQ queue before any imports so the Redis connection is never created
vi.mock("../../src/queue/backtest.queue.js", () => ({
  backtestQueue: {
    add: vi.fn().mockResolvedValue({ id: "mock-job-123" }),
  },
}));

// Mock the worker so it doesn't try to connect to Redis
vi.mock("../../src/queue/backtest.worker.js", () => ({
  startWorker: vi.fn(),
  stopWorker: vi.fn(),
}));

// Mock the WS server (not needed in HTTP-only tests)
vi.mock("../../src/websocket/server.js", () => ({
  createWsServer: vi.fn(),
  broadcast: vi.fn(),
}));

import { createApp } from "../../src/server.js";
import { initDb, closeDb } from "../../src/db/client.js";
import { backtestQueue } from "../../src/queue/backtest.queue.js";

describe("POST /lab/sessions/:id/run", () => {
  let app: Application;

  beforeAll(() => {
    initDb(":memory:");
    app = createApp();
  });

  afterAll(() => {
    closeDb();
    vi.clearAllMocks();
  });

  it("returns 404 for a non-existent session", async () => {
    const res = await request(app)
      .post("/lab/sessions/00000000-0000-0000-0000-000000000000/run")
      .send({});

    expect(res.status).toBe(404);
    expect(res.body).toMatchObject({ error: "NOT_FOUND" });
  });

  it("returns 202 and enqueues a job for an existing session", async () => {
    // Create a session first
    const createRes = await request(app)
      .post("/lab/sessions")
      .send({
        strategy_name: "test-run-strategy",
        strategy_json: JSON.stringify({ name: "test", version: "1" }),
        instruments: ["EURUSD"],
        timeframes: ["H1"],
      });
    expect(createRes.status).toBe(201);
    const sessionId = createRes.body.id as string;

    // Run it
    const runRes = await request(app)
      .post(`/lab/sessions/${sessionId}/run`)
      .send({ optimize_metric: "sharpe_ratio" });

    expect(runRes.status).toBe(202);
    expect(runRes.body).toMatchObject({
      job_id: "mock-job-123",
      session_id: sessionId,
    });
    expect(backtestQueue.add).toHaveBeenCalledOnce();
  });

  it("passes optimizer options to the queue", async () => {
    vi.mocked(backtestQueue.add).mockClear();

    const createRes = await request(app)
      .post("/lab/sessions")
      .send({
        strategy_name: "bayesian-test",
        strategy_json: JSON.stringify({ name: "bayesian", version: "1" }),
        instruments: ["GBPUSD"],
        timeframes: ["D1"],
      });
    const sessionId = createRes.body.id as string;

    await request(app)
      .post(`/lab/sessions/${sessionId}/run`)
      .send({ optimizer: "bayesian", n_trials: 20, optimize_metric: "calmar_ratio" });

    expect(backtestQueue.add).toHaveBeenCalledWith(
      "backtest",
      expect.objectContaining({
        sessionId,
        instruments: ["GBPUSD"],
        timeframes: ["D1"],
        optimizer: "bayesian",
        nTrials: 20,
        optimizeMetric: "calmar_ratio",
      })
    );
  });

  it("returns 422 for invalid optimizer value", async () => {
    const createRes = await request(app)
      .post("/lab/sessions")
      .send({
        strategy_name: "invalid-opts",
        strategy_json: JSON.stringify({ name: "x", version: "1" }),
        instruments: ["EURUSD"],
        timeframes: ["H1"],
      });
    const sessionId = createRes.body.id as string;

    const res = await request(app)
      .post(`/lab/sessions/${sessionId}/run`)
      .send({ optimizer: "invalid-optimizer" });

    expect(res.status).toBe(400);
  });
});
