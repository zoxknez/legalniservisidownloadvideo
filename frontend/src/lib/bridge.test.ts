import { describe, expect, it } from "vitest";
import { buildHrtiSessionCollectorJs } from "./bridge";

function b64url(value: object): string {
  return btoa(JSON.stringify(value))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function runCollector(storage: Record<string, string>): Record<string, string> {
  const keys = Object.keys(storage);
  const localStorage = {
    length: keys.length,
    key: (index: number) => keys[index] ?? null,
    getItem: (key: string) => storage[key] ?? null,
  };
  const token = buildHrtiSessionCollectorJs();
  return JSON.parse(Function("localStorage", "atob", `return ${token};`)(localStorage, atob));
}

describe("buildHrtiSessionCollectorJs", () => {
  it("collects token and customer metadata from JWT payload", () => {
    const jwt = `${b64url({ alg: "none" })}.${b64url({
      CustomerId: "cust-123",
      email: "user@hrti.hr",
    })}.`;

    expect(runCollector({ token: jwt })).toEqual({
      token: jwt,
      customer_id: "cust-123",
      email: "user@hrti.hr",
    });
  });

  it("falls back to localStorage JSON metadata", () => {
    expect(
      runCollector({
        token: "opaque-token-123",
        user: JSON.stringify({ Customer: { CustomerId: "cust-456" } }),
      }),
    ).toEqual({
      token: "opaque-token-123",
      customer_id: "cust-456",
    });
  });
});
