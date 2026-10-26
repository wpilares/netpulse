import type { WebSocketLike } from "./useTelemetrySocket";

export class FakeSocket implements WebSocketLike {
  static instances: FakeSocket[] = [];

  static reset(): void {
    FakeSocket.instances = [];
  }

  static at(index: number): FakeSocket {
    const socket = FakeSocket.instances[index];
    if (socket === undefined) {
      throw new Error(`No fake socket at index ${index}`);
    }
    return socket;
  }

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 0;
  readonly sent: string[] = [];
  closedByClient = false;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.closedByClient = true;
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  message(payload: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }

  serverClose(code = 1006): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { code }));
  }
}

export const createFakeSocket = (url: string): WebSocketLike => new FakeSocket(url);
