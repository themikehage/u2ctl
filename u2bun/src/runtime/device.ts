import { selectTargetDevice, forwardPort } from "./adb";
import { U2Client } from "./u2client";
import { DeviceOfflineError } from "../errors";

export class DeviceSession {
  public serial: string = "";
  public timeout: number;
  public adbPath?: string;
  public localPort: number;

  private client?: U2Client;

  constructor(serial?: string, timeout: number = 30, adbPath?: string, localPort: number = 9008) {
    if (serial) this.serial = serial;
    this.timeout = timeout;
    this.adbPath = adbPath;
    this.localPort = localPort;
  }

  async connect(): Promise<U2Client> {
    const { target } = await selectTargetDevice(this.serial, this.adbPath);
    this.serial = target.serial;

    try {
      // Forward ADB port 9008
      await forwardPort(this.serial, this.localPort, 9008, this.adbPath);
      const client = new U2Client(this.localPort, this.timeout);
      
      // Ping check
      await client.ping();
      this.client = client;
      return client;
    } catch (firstErr: any) {
      // Retry once after auto-forward
      try {
        await forwardPort(this.serial, this.localPort, 9008, this.adbPath);
        const client = new U2Client(this.localPort, this.timeout);
        await client.ping();
        this.client = client;
        return client;
      } catch (secondErr: any) {
        throw new DeviceOfflineError(
          `Failed to connect uiautomator2 to device '${this.serial}' after retry: ${secondErr.message || String(secondErr)}`
        );
      }
    }
  }

  async getClient(): Promise<U2Client> {
    if (!this.client) {
      return this.connect();
    }
    return this.client;
  }
}
