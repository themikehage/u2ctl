import { z } from "zod";
import type { DomainSpec } from "../registry";
import { registry } from "../registry";

export const TOOLS_DOMAIN: DomainSpec = {
  name: "tools",
  description: "Capability catalog introspection and schema export for external agents",
  tools: [
    {
      name: "tools.list",
      domain: "tools",
      description: "List all registered agent capabilities and their safety classes",
      inputSchema: z.object({}),
      outputSchema: z.object({
        tools: z.array(
          z.object({
            name: z.string(),
            domain: z.string(),
            description: z.string(),
            safety: z.string(),
            idempotent: z.boolean(),
          })
        ),
      }),
      safety: "read",
      handler: async () => {
        const tools = registry.listTools().map((t) => ({
          name: t.name,
          domain: t.domain,
          description: t.description,
          safety: t.safety || "read",
          idempotent: t.idempotent ?? true,
        }));
        return { tools };
      },
    },
    {
      name: "tools.show",
      domain: "tools",
      description: "Show detailed specification for a specific capability or domain",
      inputSchema: z.object({
        name: z.string().describe("Tool name (e.g. ui.tap) or domain name (e.g. ui)"),
      }),
      outputSchema: z.record(z.unknown()),
      safety: "read",
      handler: async (_, args) => {
        const target = args.name;
        const tool = registry.getTool(target);
        if (tool) {
          return {
            name: tool.name,
            domain: tool.domain,
            description: tool.description,
            safety: tool.safety || "read",
            idempotent: tool.idempotent ?? true,
            requires: tool.requires || [],
          };
        }

        const domain = registry.getDomain(target);
        if (domain) {
          return {
            domain: domain.name,
            description: domain.description,
            tools: domain.tools.map((t) => t.name),
          };
        }

        return { error: `Neither tool nor domain named '${target}' found` };
      },
    },
    {
      name: "tools.schema",
      domain: "tools",
      description: "Export full capabilities schema in machine-readable JSON format",
      inputSchema: z.object({
        format: z.enum(["openai", "raw"]).optional().default("raw"),
      }),
      outputSchema: z.record(z.unknown()),
      safety: "read",
      handler: async (_, args) => {
        const tools = registry.listTools();

        if (args.format === "openai") {
          const functions = tools.map((t) => ({
            name: t.name.replace(/\./g, "_"),
            description: t.description,
            parameters: {
              type: "object",
              properties: {},
            },
          }));
          return { functions };
        }

        const rawSpecs = tools.map((t) => ({
          name: t.name,
          domain: t.domain,
          description: t.description,
          safety: t.safety || "read",
          idempotent: t.idempotent ?? true,
        }));
        return { capabilities: rawSpecs };
      },
    },
  ],
};
