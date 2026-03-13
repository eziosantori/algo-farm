import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock BullMQ before any module imports
vi.mock("bullmq", () => ({
  Worker: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    close: vi.fn().mockResolvedValue(undefined),
  })),
}));

vi.mock("../../src/queue/connection.js", () => ({
  redisConnection: {},
}));

vi.mock("../../src/websocket/server.js", () => ({
  broadcast: vi.fn(),
}));

vi.mock("../../src/db/client.js", () => ({
  getDb: vi.fn(() => ({})),
}));

vi.mock("../../src/db/repositories/lab.repo.js", () => ({
  LabRepository: vi.fn().mockImplementation(() => ({
    updateSessionStatus: vi.fn(),
    addResult: vi.fn(),
  })),
}));

import { startWorker, stopWorker } from "../../src/queue/backtest.worker.js";
import { Worker } from "bullmq";

describe("backtest.worker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("startWorker creates a BullMQ Worker on the 'backtest' queue", () => {
    startWorker();
    expect(Worker).toHaveBeenCalledWith(
      "backtest",
      expect.any(Function),
      expect.objectContaining({ concurrency: expect.any(Number) })
    );
  });

  it("startWorker registers 'failed' and 'completed' event handlers", () => {
    startWorker();
    const instance = vi.mocked(Worker).mock.results[0]!.value as {
      on: ReturnType<typeof vi.fn>;
    };
    expect(instance.on).toHaveBeenCalledWith("failed", expect.any(Function));
    expect(instance.on).toHaveBeenCalledWith("completed", expect.any(Function));
  });

  it("stopWorker closes the worker instance", async () => {
    startWorker();
    await stopWorker();
    const instance = vi.mocked(Worker).mock.results[0]!.value as {
      close: ReturnType<typeof vi.fn>;
    };
    expect(instance.close).toHaveBeenCalled();
  });

  it("stopWorker is a no-op when called without startWorker", async () => {
    // Should not throw even if called before start
    await expect(stopWorker()).resolves.toBeUndefined();
  });
});
