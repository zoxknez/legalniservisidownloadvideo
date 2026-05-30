import { act, renderHook } from "@testing-library/react";
import { useEffect, useRef, useState } from "react";
import { useDownloadWebSocket } from "./useDownloadWebSocket";
import type { DownloadTask } from "../types/app";
import { installMockWebSocket, MockWebSocket, restoreMockWebSocket } from "../test/mockWebSocket";

vi.mock("../lib/api", () => ({
  buildWebSocketUrl: () => "ws://localhost/ws",
}));

function useQueueSocketHarness() {
  const [downloads, setDownloads] = useState<DownloadTask[]>([]);
  const [connected, setConnected] = useState(false);
  const [selectedTask, setSelectedTask] = useState<DownloadTask | null>(null);
  const selectedTaskRef = useRef<DownloadTask | null>(null);

  useEffect(() => {
    selectedTaskRef.current = selectedTask;
  }, [selectedTask]);

  const showToast = vi.fn();
  const fetchStatus = vi.fn(async () => {});

  useDownloadWebSocket({
    selectedTaskRef,
    setConnected,
    setDownloads,
    setSelectedTask,
    setSniffedItems: vi.fn(),
    setLatestSniffed: vi.fn(),
    setShowSnifferToast: vi.fn(),
    setSnifferReady: vi.fn(),
    setScheduledTasks: vi.fn(),
    showToast,
    fetchStatus,
  });

  return { downloads, connected, selectedTask, setSelectedTask, showToast, fetchStatus };
}

describe("useDownloadWebSocket", () => {
  beforeEach(() => {
    installMockWebSocket();
  });

  afterEach(() => {
    restoreMockWebSocket();
  });

  it("marks connection as open when socket connects", () => {
    const { result } = renderHook(() => useQueueSocketHarness());
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      MockWebSocket.latest().simulateOpen();
    });

    expect(result.current.connected).toBe(true);
  });

  it("applies queue_update payloads to downloads", () => {
    const queue: DownloadTask[] = [
      {
        id: "a",
        service: "voyo",
        title: "One",
        status: "downloading",
        progress: 10,
        speed: "",
        eta: "",
        logs: [],
      },
    ];

    const { result } = renderHook(() => useQueueSocketHarness());
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      MockWebSocket.latest().simulateMessage({ type: "queue_update", data: queue });
    });

    expect(result.current.downloads).toEqual(queue);
  });

  it("refreshes selected task logs when queue updates", () => {
    const initial: DownloadTask = {
      id: "a",
      service: "voyo",
      title: "One",
      status: "downloading",
      progress: 10,
      speed: "",
      eta: "",
      logs: ["old"],
    };
    const updated: DownloadTask = {
      ...initial,
      progress: 55,
      logs: ["old", "new line"],
    };

    const { result } = renderHook(() => useQueueSocketHarness());

    act(() => {
      result.current.setSelectedTask(initial);
    });

    act(() => {
      MockWebSocket.latest().simulateMessage({ type: "queue_update", data: [updated] });
    });

    expect(result.current.selectedTask).toEqual(updated);
  });

  it("calls fetchStatus after session_imported events", () => {
    const { result } = renderHook(() => useQueueSocketHarness());

    act(() => {
      MockWebSocket.latest().simulateMessage({
        type: "session_imported",
        data: { services: ["voyo"], message: "Imported" },
      });
    });

    expect(result.current.showToast).toHaveBeenCalledWith("Imported", "success");
    expect(result.current.fetchStatus).toHaveBeenCalled();
  });
});
