import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import request from "supertest";
import { createApp } from "../../src/server.js";
import { initDb, closeDb } from "../../src/db/client.js";
import type { Application } from "express";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

const validStrategy: StrategyDefinition = {
  version: "1.0",
  name: "Integration Test Strategy",
  variant: "basic",
  indicators: [{ name: "rsi14", type: "rsi", params: { period: 14 } }],
  entry_rules: [{ indicator: "rsi14", condition: "<", value: 30 }],
  exit_rules: [{ indicator: "rsi14", condition: ">", value: 70 }],
  position_management: { size: 0.02, max_open_trades: 1 },
};

describe("Strategies Routes", () => {
  let app: Application;

  beforeAll(() => {
    initDb(":memory:");
    app = createApp();
  });

  afterAll(() => {
    closeDb();
  });

  describe("GET /health", () => {
    it("returns status ok", async () => {
      const res = await request(app).get("/health");
      expect(res.status).toBe(200);
      expect(res.body).toEqual({ status: "ok" });
    });
  });

  describe("POST /strategies", () => {
    it("creates a strategy and returns 201", async () => {
      const res = await request(app).post("/strategies").send(validStrategy);
      expect(res.status).toBe(201);
      expect(res.body.id).toBeTruthy();
      expect(res.body.created_at).toBeTruthy();
    });

    it("returns 400 for invalid strategy", async () => {
      const res = await request(app)
        .post("/strategies")
        .send({ name: "Bad" });
      expect(res.status).toBe(400);
      expect(res.body.error).toBe("SCHEMA_VALIDATION_ERROR");
    });
  });

  describe("GET /strategies", () => {
    it("returns a list of strategies", async () => {
      const res = await request(app).get("/strategies");
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.strategies)).toBe(true);
    });
  });

  describe("GET /strategies/:id", () => {
    it("returns 404 for non-existent id", async () => {
      const res = await request(app).get("/strategies/non-existent");
      expect(res.status).toBe(404);
    });

    it("returns a strategy by id", async () => {
      const create = await request(app).post("/strategies").send(validStrategy);
      const { id } = create.body;

      const res = await request(app).get(`/strategies/${id}`);
      expect(res.status).toBe(200);
      expect(res.body.definition.name).toBe("Integration Test Strategy");
    });
  });

  describe("PUT /strategies/:id", () => {
    it("updates a strategy", async () => {
      const create = await request(app).post("/strategies").send(validStrategy);
      const { id } = create.body;

      const res = await request(app)
        .put(`/strategies/${id}`)
        .send({ ...validStrategy, name: "Updated Strategy" });
      expect(res.status).toBe(200);

      const get = await request(app).get(`/strategies/${id}`);
      expect(get.body.definition.name).toBe("Updated Strategy");
    });

    it("returns 404 for non-existent id", async () => {
      const res = await request(app)
        .put("/strategies/non-existent")
        .send(validStrategy);
      expect(res.status).toBe(404);
    });
  });

  describe("DELETE /strategies/:id", () => {
    it("deletes a strategy and returns 204", async () => {
      const create = await request(app).post("/strategies").send(validStrategy);
      const { id } = create.body;

      const res = await request(app).delete(`/strategies/${id}`);
      expect(res.status).toBe(204);

      const get = await request(app).get(`/strategies/${id}`);
      expect(get.status).toBe(404);
    });
  });
});
