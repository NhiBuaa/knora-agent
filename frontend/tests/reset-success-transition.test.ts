// @vitest-environment node
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const script = readFileSync(
  new URL(
    "../../themes/knora/login/resources/js/knora-login-transition.js",
    import.meta.url,
  ),
  "utf8",
);
const key = "knora:reset-success:knora:knora-web";

function fixture(completion = false) {
  const storage = new Map<string, string>();
  const notice = { hidden: true, getAttribute: () => key };
  const replace = vi.fn();
  const window = {
    sessionStorage: {
      getItem: (name: string) => storage.get(name) ?? null,
      removeItem: (name: string) => storage.delete(name),
      setItem: (name: string, value: string) => storage.set(name, value),
    },
    location: { replace },
  };
  const context = {
    window,
    document: {
      querySelector: () =>
        completion
          ? {
              getAttribute: (name: string) =>
                name === "href"
                  ? "https://app.example/api/auth/login?prompt=login"
                  : key,
            }
          : null,
      getElementById: () => (completion ? null : notice),
    },
    Date: { now: () => 1000 },
  };
  return {
    storage,
    notice,
    replace,
    window,
    run: () => runInNewContext(script, context),
  };
}

describe("native reset-success presentation", () => {
  it("starts fresh login with only an expiring cosmetic marker", () => {
    const f = fixture(true);
    f.run();
    expect(JSON.parse(f.storage.get(key)!)).toEqual({ expiresAt: 121000 });
    expect(f.replace).toHaveBeenCalledWith(
      "https://app.example/api/auth/login?prompt=login",
    );
  });
  it("consumes a valid notice once without authenticating or navigating", () => {
    const f = fixture();
    f.storage.set(key, JSON.stringify({ expiresAt: 2000 }));
    f.run();
    expect(f.notice.hidden).toBe(false);
    expect(f.storage.has(key)).toBe(false);
    f.notice.hidden = true;
    f.run();
    expect(f.notice.hidden).toBe(true);
    expect(f.replace).not.toHaveBeenCalled();
  });
  it.each(["{", "null", '{"expiresAt":1000}', '{"expiresAt":"2000"}'])(
    "discards unusable marker %s without a success notice",
    (marker) => {
      const f = fixture();
      f.storage.set(key, marker);
      f.run();
      expect(f.notice.hidden).toBe(true);
      expect(f.storage.has(key)).toBe(false);
    },
  );
  it.each([true, false])(
    "retains fallback with blocked storage (completion=%s)",
    (completion) => {
      const f = fixture(completion);
      Object.defineProperty(f.window, "sessionStorage", {
        get() {
          throw new Error("Storage denied");
        },
      });
      expect(f.run).not.toThrow();
      expect(f.replace).not.toHaveBeenCalled();
      expect(f.notice.hidden).toBe(true);
    },
  );
});
