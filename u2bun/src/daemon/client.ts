import { existsSync, readFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";
import { getDaemonConfigPath, type DaemonInfo } from "./server";

export class DaemonClient {
  public serial: string;
  private port: number | null = null;

  constructor(serial: string) {
    this.serial = serial;
  }

  private async getActivePort(): Promise<number | null> {
    const configPath = getDaemonConfigPath(this.serial);
    if (!existsSync(configPath)) return null;

    try {
      const content = readFileSync(configPath, "utf-8");
      const info: DaemonInfo = JSON.parse(content);
      const res = await fetch(`http://127.0.0.1:${info.port}/ping`, { signal: AbortSignal.timeout(1000) });
      if (res.ok) {
        const data: any = await res.json();
        if (data.ok && data.serial === this.serial) {
          return info.port;
        }
      }
    } catch {}

    return null;
  }

  public async ensureDaemon(): Promise<number> {
    let port = await this.getActivePort();
    if (port !== null) {
      this.port = port;
      return port;
    }

    const serverScript = join(__dirname, "server.ts");
    const child = spawn("bun", ["run", serverScript, "--serial", this.serial], {
      detached: true,
      stdio: "ignore",
      env: process.env,
    });
    child.unref();

    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 100));
      port = await this.getActivePort();
      if (port !== null) {
        this.port = port;
        return port;
      }
    }

    throw new Error(`Failed to start u2bun daemon for device '${this.serial}'`);
  }

  public async snapshot(args: Record<string, unknown> = {}): Promise<any> {
    const port = await this.ensureDaemon();
    const res = await fetch(`http://127.0.0.1:${port}/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(`Daemon snapshot failed: ${err.error || res.statusText}`);
    }
    return await res.json();
  }

  public async action(command: string, args: Record<string, unknown> = {}): Promise<any> {
    const port = await this.ensureDaemon();
    const res = await fetch(`http://127.0.0.1:${port}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, args }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(`Daemon action failed: ${err.error || res.statusText}`);
    }
    return await res.json();
  }
}
