import { z } from "zod";
import type { DomainSpec } from "../registry";
import { selectTargetDevice, listAdbDevices, reconnectDevice, execAdb } from "../runtime/adb";
import { DeviceSession } from "../runtime/device";

export const DEVICE_DOMAIN: DomainSpec = {
  name: "device",
  description: "Device discovery, status, inspection, and connection recovery",
  tools: [
    {
      name: "device.list",
      domain: "device",
      description: "List all connected ADB devices with status and transport type",
      inputSchema: z.object({}),
      outputSchema: z.object({
        devices: z.array(
          z.object({
            serial: z.string(),
            state: z.string(),
            model: z.string(),
            transport: z.string(),
            selected: z.boolean().optional(),
          })
        ),
      }),
      safety: "read",
      handler: async (ctx) => {
        const devices = await listAdbDevices();
        return { devices };
      },
    },
    {
      name: "device.status",
      domain: "device",
      description: "Check status and selected state of target device",
      inputSchema: z.object({}),
      outputSchema: z.object({
        serial: z.string(),
        state: z.string(),
        model: z.string(),
        transport: z.string(),
        ready: z.boolean(),
      }),
      safety: "read",
      handler: async (ctx) => {
        const { target } = await selectTargetDevice(ctx.serial);
        ctx.serial = target.serial;
        return {
          serial: target.serial,
          state: target.state,
          model: target.model,
          transport: target.transport,
          ready: target.state === "device",
        };
      },
    },
    {
      name: "device.info",
      domain: "device",
      description: "Get detailed Android device metadata and uiautomator2 runtime info",
      inputSchema: z.object({}),
      outputSchema: z.object({
        serial: z.string(),
        model: z.string(),
        sdk_version: z.string(),
        screen_on: z.boolean(),
        display_width: z.number(),
        display_height: z.number(),
        current_package: z.string(),
      }),
      safety: "read",
      handler: async (ctx) => {
        const session = new DeviceSession(ctx.serial, ctx.timeout);
        const client = await session.connect();
        ctx.serial = session.serial;

        const info = await client.deviceInfo();
        const { stdout: sdkOut } = await execAdb(["-s", session.serial, "shell", "getprop", "ro.build.version.sdk"]);

        return {
          serial: session.serial,
          model: info.productName || "unknown",
          sdk_version: sdkOut.trim(),
          screen_on: info.screenOn ?? true,
          display_width: info.displayWidth || 0,
          display_height: info.displayHeight || 0,
          current_package: info.currentPackageName || "",
        };
      },
    },
    {
      name: "device.reconnect",
      domain: "device",
      description: "Perform soft reconnect or hard adb server restart to recover device connection",
      inputSchema: z.object({
        hard: z.boolean().optional().default(false),
      }),
      outputSchema: z.object({
        message: z.string(),
      }),
      safety: "interactive",
      expect: {
        schema: z.object({ message: z.string() }),
      },
      handler: async (ctx, args) => {
        const { target } = await selectTargetDevice(ctx.serial);
        ctx.serial = target.serial;
        const msg = await reconnectDevice(target.serial, args.hard);
        return { message: msg };
      },
    },
  ],
};
