import "dotenv/config";
import { fileURLToPath } from "url";
import express from "express";
import cors from "cors";
import { initDb } from "./db/client.js";
import healthRouter from "./routes/health.js";
import strategiesRouter from "./routes/strategies.js";
import wizardRouter from "./routes/wizard.js";

const PORT = parseInt(process.env.PORT ?? "3001", 10);
const DB_PATH = process.env.DB_PATH ?? "./algo_farm.db";

export function createApp(): express.Application {
  const app = express();

  app.use(cors());
  app.use(express.json());

  app.use(healthRouter);
  app.use(strategiesRouter);
  app.use(wizardRouter);

  return app;
}

// Only start the server when this module is the entry point
const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] === currentFile) {
  initDb(DB_PATH);
  const app = createApp();
  app.listen(PORT, () => {
    console.log(`API server running on http://localhost:${PORT}`);
  });
}
