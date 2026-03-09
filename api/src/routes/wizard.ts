import { Router, Request, Response } from "express";
import { z } from "zod";
import { WizardService } from "../services/wizard.service.js";
import { openRouterModelsService } from "../services/openrouter-models.service.js";
import { validateBody } from "../middleware/validate.js";

const router = Router();

const ChatRequestSchema = z.object({
  message: z.string().min(1, "Message cannot be empty"),
  provider: z.enum(["claude", "gemini", "openrouter"]).default("gemini"),
  model: z.string().min(1).optional(),
});

const wizardService = new WizardService();

router.post(
  "/wizard/chat",
  validateBody(ChatRequestSchema),
  async (req: Request, res: Response): Promise<void> => {
    try {
      const { message, provider, model } = req.body as {
        message: string;
        provider: "claude" | "gemini" | "openrouter";
        model?: string;
      };
      const result = await wizardService.chat(message, provider, { model });
      res.json(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";

      if (message.startsWith("LLM_API_ERROR")) {
        res.status(500).json({ error: "LLM_API_ERROR", message });
        return;
      }

      if (message.startsWith("SCHEMA_VALIDATION_ERROR")) {
        res.status(400).json({ error: "SCHEMA_VALIDATION_ERROR", message });
        return;
      }

      res.status(500).json({ error: "INTERNAL_ERROR", message });
    }
  }
);

router.get("/wizard/openrouter/models", async (_req: Request, res: Response): Promise<void> => {
  try {
    const models = await openRouterModelsService.listFreeModels();
    res.json(models);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    res.status(500).json({ error: "LLM_API_ERROR", message });
  }
});

export default router;
