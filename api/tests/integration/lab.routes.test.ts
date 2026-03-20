import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import { createApp } from "../../src/server.js";
import { initDb, closeDb } from "../../src/db/client.js";
import type { Application } from "express";

const sampleMetrics = {
  total_return_pct: 5.2, sharpe_ratio: 1.4, sortino_ratio: 1.8,
  calmar_ratio: 1.1, max_drawdown_pct: -4.7, win_rate_pct: 58.0,
  profit_factor: 1.6, total_trades: 42, avg_trade_duration_bars: 18,
  cagr_pct: 3.1, expectancy: 12.4,
};

const validSession = {
  strategy_name: "SuperTrend + RSI",
  strategy_json: JSON.stringify({ version: "1", name: "SuperTrend + RSI" }),
  instruments: ["EURUSD", "XAUUSD"],
  timeframes: ["H1", "M15"],
  constraints: { min_sharpe: 1.2 },
};

describe("Lab Routes", () => {
  let app: Application;

  beforeAll(() => {
    initDb(":memory:");
    app = createApp();
  });

  afterAll(() => {
    closeDb();
  });

  // --- Sessions -------------------------------------------------------------

  describe("POST /lab/sessions", () => {
    it("creates a session and returns 201 with id", async () => {
      const res = await request(app).post("/lab/sessions").send(validSession);
      expect(res.status).toBe(201);
      expect(res.body.id).toBeTruthy();
    });

    it("rejects missing strategy_name with 400", async () => {
      const res = await request(app)
        .post("/lab/sessions")
        .send({ ...validSession, strategy_name: "" });
      expect(res.status).toBe(400);
    });

    it("rejects empty instruments array with 400", async () => {
      const res = await request(app)
        .post("/lab/sessions")
        .send({ ...validSession, instruments: [] });
      expect(res.status).toBe(400);
    });
  });

  describe("GET /lab/sessions", () => {
    it("returns sessions list", async () => {
      const res = await request(app).get("/lab/sessions");
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.sessions)).toBe(true);
    });
  });

  describe("GET /lab/sessions/:id", () => {
    it("returns session detail with results array", async () => {
      const { body: { id } } = await request(app).post("/lab/sessions").send(validSession);
      const res = await request(app).get(`/lab/sessions/${id}`);
      expect(res.status).toBe(200);
      expect(res.body.id).toBe(id);
      expect(Array.isArray(res.body.results)).toBe(true);
      expect(res.body.constraints).toEqual({ min_sharpe: 1.2 });
    });

    it("returns 404 for unknown session", async () => {
      const res = await request(app).get("/lab/sessions/nope");
      expect(res.status).toBe(404);
    });
  });

  describe("PATCH /lab/sessions/:id/status", () => {
    it("marks session as completed", async () => {
      const { body: { id } } = await request(app).post("/lab/sessions").send(validSession);
      const res = await request(app)
        .patch(`/lab/sessions/${id}/status`)
        .send({ status: "completed" });
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
    });
  });

  // --- Results --------------------------------------------------------------

  describe("POST /lab/sessions/:id/results", () => {
    it("adds a result and returns 201 with id", async () => {
      const { body: { id: sessionId } } = await request(app)
        .post("/lab/sessions")
        .send(validSession);

      const res = await request(app)
        .post(`/lab/sessions/${sessionId}/results`)
        .send({
          instrument: "EURUSD",
          timeframe: "H1",
          params_json: JSON.stringify({ period: 10, multiplier: 3 }),
          metrics_json: JSON.stringify(sampleMetrics),
        });

      expect(res.status).toBe(201);
      expect(res.body.id).toBeTruthy();
    });

    it("returns 404 for unknown session", async () => {
      const res = await request(app)
        .post("/lab/sessions/nope/results")
        .send({
          instrument: "EURUSD", timeframe: "H1",
          params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
        });
      expect(res.status).toBe(404);
    });
  });

  describe("PATCH /lab/results/:id/status", () => {
    it("updates result status to validated", async () => {
      const { body: { id: sessionId } } = await request(app)
        .post("/lab/sessions").send(validSession);
      const { body: { id: resultId } } = await request(app)
        .post(`/lab/sessions/${sessionId}/results`)
        .send({
          instrument: "EURUSD", timeframe: "H1",
          params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
        });

      const res = await request(app)
        .patch(`/lab/results/${resultId}/status`)
        .send({ status: "validated" });

      expect(res.status).toBe(200);
      expect(res.body.status).toBe("validated");
    });

    it("updates result status to production_standard", async () => {
      const { body: { id: sessionId } } = await request(app)
        .post("/lab/sessions").send(validSession);
      const { body: { id: resultId } } = await request(app)
        .post(`/lab/sessions/${sessionId}/results`)
        .send({
          instrument: "EURUSD", timeframe: "H1",
          params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
        });

      const res = await request(app)
        .patch(`/lab/results/${resultId}/status`)
        .send({ status: "production_standard" });

      expect(res.status).toBe(200);
      expect(res.body.status).toBe("production_standard");
    });

    it("rejects invalid status with 400", async () => {
      const res = await request(app)
        .patch("/lab/results/any-id/status")
        .send({ status: "invalid_status" });
      expect(res.status).toBe(400);
    });

    it("returns 404 for unknown result", async () => {
      const res = await request(app)
        .patch("/lab/results/nope/status")
        .send({ status: "validated" });
      expect(res.status).toBe(404);
    });
  });

  // --- Notes ----------------------------------------------------------------

  describe("PATCH /lab/sessions/:id/notes", () => {
    it("saves research notes and returns 200 with success:true", async () => {
      const { body: { id } } = await request(app).post("/lab/sessions").send(validSession);
      const res = await request(app)
        .patch(`/lab/sessions/${id}/notes`)
        .send({ research_notes: "## Test\n- Sharpe 1.2" });
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
    });

    it("returns 404 for non-existent session id", async () => {
      const res = await request(app)
        .patch("/lab/sessions/nope/notes")
        .send({ research_notes: "some notes" });
      expect(res.status).toBe(404);
    });

    it("rejects empty research_notes string with 400", async () => {
      const { body: { id } } = await request(app).post("/lab/sessions").send(validSession);
      const res = await request(app)
        .patch(`/lab/sessions/${id}/notes`)
        .send({ research_notes: "" });
      expect(res.status).toBe(400);
    });
  });
});
