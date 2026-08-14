import { tmpdir } from "node:os";
import { join } from "node:path";
import { writeFileSync, unlinkSync, existsSync } from "node:fs";
import { DeviceSession } from "../runtime/device";
import type { ActionElement } from "../models";
import { parseXmlDump, computeScreenFingerprint, formatCompactSnapshot, checkExpect } from "../domains/ui";
import { parseSelectorArgs } from "../selectors/parser";
import { resolveSelector } from "../selectors/resolver";

export function getDaemonConfigPath(serial: string): string {
  const safeSerial = serial.replace(/[^a-zA-Z0-9_\-]/g, "_");
  return join(tmpdir(), `u2bun-daemon-${safeSerial}.json`);
}

export interface DaemonInfo {
  port: number;
  pid: number;
  serial: string;
}

export class DaemonServer {
  public serial: string;
  public port: number;
  private session: DeviceSession | null = null;
  private elements: ActionElement[] = [];
  private handles: Map<string, ActionElement> = new Map();
  private fingerprint: string = "";
  private prevSnapshotLines: string[] = [];
  private server: ReturnType<typeof Bun.serve> | null = null;

  constructor(serial: string, port: number = 0) {
    this.serial = serial;
    this.port = port;
  }

  private async getSession(): Promise<DeviceSession> {
    if (!this.session) {
      this.session = new DeviceSession(this.serial);
    }
    await this.session.connect();
    return this.session;
  }

  public async start(): Promise<DaemonInfo> {
    const self = this;
    this.server = Bun.serve({
      port: this.port,
      hostname: "127.0.0.1",
      async fetch(req) {
        const url = new URL(req.url);

        if (url.pathname === "/ping") {
          return Response.json({ ok: true, serial: self.serial, pid: process.pid });
        }

        if (url.pathname === "/snapshot" && req.method === "POST") {
          try {
            const body = await req.json().catch(() => ({}));
            const includeSystemBars = Boolean(body.include_system_bars);
            const session = await self.getSession();
            const client = session.client!;

            let packageName: string | undefined = undefined;
            try {
              const info = await client.deviceInfo();
              packageName = info.currentPackageName;
            } catch {}

            const xml = await client.dumpHierarchy();
            let rawElements = parseXmlDump(xml, includeSystemBars);

            if (body.limit && body.limit > 0 && rawElements.length > body.limit) {
              rawElements = rawElements.slice(0, body.limit);
            }

            self.handles.clear();
            self.elements = rawElements.map((el, i) => {
              const ref = `@${i + 1}`;
              const item = { ...el, ref, index: i };
              self.handles.set(ref, item);
              return item;
            });

            const newFingerprint = computeScreenFingerprint(self.elements);
            const hasPrev = self.fingerprint !== "";
            const changed = hasPrev ? self.fingerprint !== newFingerprint : undefined;
            self.fingerprint = newFingerprint;

            let snapshotText = formatCompactSnapshot(
              self.elements,
              packageName,
              body.fingerprint ? self.fingerprint : undefined,
              changed
            );

            if (body.diff && hasPrev && self.prevSnapshotLines.length > 0) {
              const currentLines = snapshotText.split("\n");
              const header = currentLines[0];
              const prevSet = new Set(self.prevSnapshotLines.slice(1));
              const changedLines = currentLines.slice(1).filter((line) => !prevSet.has(line));
              snapshotText = [header, ...changedLines].join("\n");
            }
            self.prevSnapshotLines = snapshotText.split("\n");

            const handleObj: Record<string, unknown> = {};
            if (body.include_handles) {
              self.handles.forEach((v, k) => {
                handleObj[k] = { text: v.text, resourceId: v.resourceId, bounds: v.bounds };
              });
            }

            return Response.json({
              ok: true,
              screen_fingerprint: self.fingerprint,
              element_count: self.elements.length,
              snapshot: snapshotText,
              ...(body.include_handles ? { handles: handleObj } : {}),
            });
          } catch (err: any) {
            return Response.json({ ok: false, error: err.message }, { status: 500 });
          }
        }

        if (url.pathname === "/action" && req.method === "POST") {
          try {
            const body = await req.json();
            const { command, args } = body;
            const session = await self.getSession();
            const client = session.client!;

            if (command === "tap") {
              let matched: ReturnType<typeof resolveSelector>;
              
              if (args.ref && self.handles.has(args.ref)) {
                const el = self.handles.get(args.ref)!;
                matched = resolveSelector([el], { ref: args.ref });
              } else {
                if (self.elements.length === 0) {
                  const xml = await client.dumpHierarchy();
                  self.elements = parseXmlDump(xml, true);
                }
                const query = parseSelectorArgs(args);
                matched = resolveSelector(self.elements, query);
              }

              const preFingerprint = self.fingerprint;
              await client.click(matched.centerX, matched.centerY);

              const hasExpect = Boolean(args.expect_desc_contains || args.expect_text_contains || args.expect_element_absent);
              const postcondition: Record<string, unknown> = {};

              if (hasExpect) {
                const postXml = await client.dumpHierarchy();
                const postElements = parseXmlDump(postXml, true);
                const postFingerprint = computeScreenFingerprint(postElements);
                self.fingerprint = postFingerprint;
                postcondition.screen_changed = preFingerprint !== postFingerprint;
                postcondition.screen_fingerprint = postFingerprint;

                const [satisfied, matchedElem] = checkExpect(args, postElements);
                postcondition.expect_satisfied = satisfied;
                if (matchedElem) postcondition.matched_element = matchedElem;
              }

              return Response.json({
                ok: true,
                result: {
                  tapped: true,
                  x: matched.centerX,
                  y: matched.centerY,
                  ...(hasExpect ? { postcondition } : {}),
                },
              });
            }

            return Response.json({ ok: false, error: `Unknown daemon command: ${command}` }, { status: 400 });
          } catch (err: any) {
            return Response.json({ ok: false, error: err.message }, { status: 500 });
          }
        }

        if (url.pathname === "/shutdown" && req.method === "POST") {
          self.stop();
          return Response.json({ ok: true, message: "Daemon shutting down" });
        }

        return Response.json({ ok: false, error: "Not found" }, { status: 404 });
      },
    });

    const info: DaemonInfo = {
      port: this.server.port,
      pid: process.pid,
      serial: this.serial,
    };

    const configPath = getDaemonConfigPath(this.serial);
    writeFileSync(configPath, JSON.stringify(info, null, 2), "utf-8");

    return info;
  }

  public stop(): void {
    if (this.server) {
      this.server.stop();
      this.server = null;
    }
    const configPath = getDaemonConfigPath(this.serial);
    if (existsSync(configPath)) {
      try {
        unlinkSync(configPath);
      } catch {}
    }
  }
}

if (import.meta.main) {
  const serialIdx = process.argv.indexOf("--serial");
  const serial = serialIdx !== -1 ? process.argv[serialIdx + 1] : "";
  if (!serial) {
    console.error("Usage: bun run server.ts --serial <SERIAL>");
    process.exit(1);
  }

  const server = new DaemonServer(serial);
  server.start().then((info) => {
    console.log(`u2bun daemon started for device ${info.serial} on port ${info.port} (PID ${info.pid})`);
  });
}
