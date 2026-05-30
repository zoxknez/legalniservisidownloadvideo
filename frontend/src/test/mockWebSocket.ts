export class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  simulateOpen() {
    this.onopen?.();
  }

  simulateMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
  }

  simulateClose() {
    this.onclose?.();
  }

  static latest(): MockWebSocket {
    const socket = MockWebSocket.instances.at(-1);
    if (!socket) throw new Error("No MockWebSocket instance created");
    return socket;
  }

  static reset() {
    MockWebSocket.instances = [];
  }
}

export function installMockWebSocket() {
  MockWebSocket.reset();
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
}

export function restoreMockWebSocket() {
  vi.unstubAllGlobals();
  MockWebSocket.reset();
}
