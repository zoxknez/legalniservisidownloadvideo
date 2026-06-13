import { describe, expect, it } from "vitest";
import { getApiHostForLocation, getWebSocketHostForLocation } from "./api";

describe("api host resolution", () => {
  it("uses Vite proxy during local dev", () => {
    expect(getApiHostForLocation("localhost", "5173")).toBe("");
    expect(getWebSocketHostForLocation("localhost", "5173", "localhost:5173")).toBe("localhost:5173");
  });

  it("routes localhost preview/custom ports to backend port", () => {
    expect(getApiHostForLocation("localhost", "4173")).toBe("http://127.0.0.1:8200");
    expect(getApiHostForLocation("127.0.0.1", "3000")).toBe("http://127.0.0.1:8200");
    expect(getWebSocketHostForLocation("localhost", "4173", "localhost:4173")).toBe("localhost:8200");
  });

  it("keeps remote hosts same-origin", () => {
    expect(getApiHostForLocation("192.168.1.20", "8200")).toBe("");
    expect(getWebSocketHostForLocation("192.168.1.20", "8200", "192.168.1.20:8200")).toBe("192.168.1.20:8200");
  });
});
