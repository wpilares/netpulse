import { useEffect, useReducer, useRef } from "react";
import { type KpiFrame, type LiveFrame, parseLiveFrame } from "./frames";
import { appendHistory, emptyHistory, type PortHistory } from "./history";

export interface WebSocketLike {
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  readonly readyState: number;
  send(data: string): void;
  close(): void;
}

export type SocketStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface BackoffOptions {
  readonly baseMs: number;
  readonly maxMs: number;
  readonly jitterMs: number;
}

export interface TelemetrySocketOptions {
  readonly url?: string;
  readonly createSocket?: (url: string) => WebSocketLike;
  readonly maxPoints?: number;
  readonly backoff?: BackoffOptions;
  readonly pingIntervalMs?: number;
  readonly random?: () => number;
}

export interface TelemetrySocketState {
  readonly status: SocketStatus;
  readonly latest: KpiFrame | null;
  readonly history: PortHistory;
  readonly storeUnavailable: boolean;
  readonly lastHeartbeatAt: string | null;
  readonly attempt: number;
}

type Action =
  | { readonly type: "open" }
  | { readonly type: "frame"; readonly frame: LiveFrame; readonly maxPoints: number }
  | { readonly type: "reconnecting"; readonly attempt: number }
  | { readonly type: "closed" };

const DEFAULT_BACKOFF: BackoffOptions = { baseMs: 1000, maxMs: 30_000, jitterMs: 500 };
const DEFAULT_PING_INTERVAL_MS = 15_000;
const DEFAULT_MAX_POINTS = 120;
const TELEMETRY_PATH = "/ws/telemetry";

const initialState: TelemetrySocketState = {
  status: "connecting",
  latest: null,
  history: emptyHistory,
  storeUnavailable: false,
  lastHeartbeatAt: null,
  attempt: 0,
};

export const telemetrySocketUrl = (location: { readonly protocol: string; readonly host: string }): string =>
  `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}${TELEMETRY_PATH}`;

export const reconnectDelayMs = (attempt: number, backoff: BackoffOptions, random: () => number): number =>
  Math.min(backoff.baseMs * 2 ** attempt, backoff.maxMs) + Math.floor(random() * backoff.jitterMs);

const createBrowserSocket = (url: string): WebSocketLike => new WebSocket(url);

const applyFrame = (state: TelemetrySocketState, frame: LiveFrame, maxPoints: number): TelemetrySocketState => {
  switch (frame.type) {
    case "kpis":
      return {
        ...state,
        latest: frame,
        history: appendHistory(state.history, frame, maxPoints),
        storeUnavailable: false,
      };
    case "heartbeat":
      return { ...state, lastHeartbeatAt: frame.at };
    case "store_unavailable":
      return { ...state, lastHeartbeatAt: frame.at, storeUnavailable: true };
    case "hello":
    case "pong":
    case "error":
      return state;
  }
};

const reduce = (state: TelemetrySocketState, action: Action): TelemetrySocketState => {
  switch (action.type) {
    case "open":
      return { ...state, status: "open", attempt: 0 };
    case "frame":
      return applyFrame(state, action.frame, action.maxPoints);
    case "reconnecting":
      return { ...state, status: "reconnecting", attempt: action.attempt };
    case "closed":
      return { ...state, status: "closed" };
  }
};

const parseMessage = (data: unknown): LiveFrame | null => {
  if (typeof data !== "string") {
    return null;
  }
  try {
    return parseLiveFrame(JSON.parse(data));
  } catch {
    return null;
  }
};

export const useTelemetrySocket = ({
  url = telemetrySocketUrl(window.location),
  createSocket = createBrowserSocket,
  maxPoints = DEFAULT_MAX_POINTS,
  backoff = DEFAULT_BACKOFF,
  pingIntervalMs = DEFAULT_PING_INTERVAL_MS,
  random = Math.random,
}: TelemetrySocketOptions = {}): TelemetrySocketState => {
  const [state, dispatch] = useReducer(reduce, initialState);
  const { baseMs, maxMs, jitterMs } = backoff;
  const callbacks = useRef({ createSocket, random });

  useEffect(() => {
    callbacks.current = { createSocket, random };
  });

  useEffect(() => {
    let socket: WebSocketLike | null = null;
    let reconnectTimer: number | null = null;
    let pingTimer: number | null = null;
    let attempt = 0;
    let disposed = false;

    const stopPing = () => {
      if (pingTimer !== null) {
        window.clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const connect = () => {
      const current = callbacks.current.createSocket(url);
      socket = current;
      current.onopen = () => {
        attempt = 0;
        dispatch({ type: "open" });
        pingTimer = window.setInterval(() => current.send("ping"), pingIntervalMs);
      };
      current.onmessage = (event) => {
        const frame = parseMessage(event.data);
        if (frame !== null) {
          dispatch({ type: "frame", frame, maxPoints });
        }
      };
      current.onclose = () => {
        stopPing();
        if (disposed) {
          return;
        }
        const delay = reconnectDelayMs(attempt, { baseMs, maxMs, jitterMs }, callbacks.current.random);
        attempt += 1;
        dispatch({ type: "reconnecting", attempt });
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      disposed = true;
      stopPing();
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
      dispatch({ type: "closed" });
    };
  }, [url, maxPoints, baseMs, maxMs, jitterMs, pingIntervalMs]);

  return state;
};
