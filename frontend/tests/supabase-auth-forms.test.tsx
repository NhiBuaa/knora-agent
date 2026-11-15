import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { LoginForm } from "@/components/auth/LoginForm";
import { AuthFrame } from "@/components/auth/AuthFrame";
import ForgotPasswordPage from "@/app/auth/forgot-password/page";
import ResetCodePage from "@/app/auth/reset-code/page";
import NewPasswordPage from "@/app/auth/new-password/page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => ({
    get: (key: string) => (key === "email" ? "recovery@example.test" : null),
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("RegisterForm", () => {
  it("rejects mismatched confirmation before sending registration", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.type(screen.getByLabelText("Email"), "demo@example.test");
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      "Password-1",
    );
    await user.type(screen.getByLabelText("Confirm password"), "Password-2");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Passwords do not match",
    );
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("submits valid registration and redirects to workspace", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, redirect: "/workspaces" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<RegisterForm />);

    await user.type(screen.getByLabelText("Email"), "newuser@example.test");
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      "Password-123",
    );
    await user.type(screen.getByLabelText("Confirm password"), "Password-123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/register");
    expect(JSON.parse(opts.body)).toMatchObject({
      email: "newuser@example.test",
      password: "Password-123",
    });
    expect(pushMock).toHaveBeenCalledWith("/workspaces");
  });

  it("displays server error alert on failed registration", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ error: "User already registered with this email" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<RegisterForm />);

    await user.type(screen.getByLabelText("Email"), "existing@example.test");
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      "Password-123",
    );
    await user.type(screen.getByLabelText("Confirm password"), "Password-123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "User already registered with this email",
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe("LoginForm", () => {
  it("renders accessible labels, links and inputs", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText("Email")).toBeVisible();
    expect(screen.getByLabelText("Password", { exact: true })).toBeVisible();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Forgot your password?" }),
    ).toHaveAttribute("href", "/auth/forgot-password");
    expect(
      screen.getByRole("link", { name: "Create account" }),
    ).toHaveAttribute("href", "/auth/register");
  });

  it("submits login form and handles successful sign-in", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, redirect: "/workspaces" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "user@example.test");
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      "Secret123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/login");
    expect(JSON.parse(opts.body)).toEqual({
      email: "user@example.test",
      password: "Secret123!",
    });
    expect(pushMock).toHaveBeenCalledWith("/workspaces");
  });

  it("displays alert on invalid credentials (401)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Invalid credentials" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "wrong@example.test");
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      "WrongPass",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sign-in details weren’t accepted",
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe("AuthFrame", () => {
  it("renders Knora brand cues, mark and responsive layout", () => {
    render(
      <AuthFrame>
        <div>Content Inside Frame</div>
      </AuthFrame>,
    );
    expect(screen.getByRole("complementary", { name: "Knora" })).toBeVisible();
    expect(screen.getByText("EVIDENCE-FIRST KNOWLEDGE")).toBeVisible();
    expect(screen.getByText("SOURCES")).toBeVisible();
    expect(screen.getByText("PAGE RANGES")).toBeVisible();
    expect(screen.getByText("PROVENANCE")).toBeVisible();
    expect(screen.getByText("Content Inside Frame")).toBeVisible();
  });
});

describe("Recovery Forms", () => {
  it("submits forgot password request and navigates to reset-code", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<ForgotPasswordPage />);

    expect(
      screen.getByRole("heading", { name: "Forgot your password?" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Email"), "user@example.test");
    await user.click(
      screen.getByRole("button", { name: "Send verification code" }),
    );

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/recovery/request");
    expect(JSON.parse(opts.body)).toEqual({ email: "user@example.test" });
    expect(pushMock).toHaveBeenCalledWith(
      "/auth/reset-code?email=user%40example.test",
    );
  });

  it("submits reset code verification and navigates to new-password", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ success: true, redirect: "/auth/new-password" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<ResetCodePage />);

    expect(
      screen.getByRole("heading", { name: "Enter verification code" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Six-digit reset code"), "654321");
    await user.click(screen.getByRole("button", { name: "Verify code" }));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/recovery/verify");
    expect(JSON.parse(opts.body)).toEqual({
      email: "recovery@example.test",
      code: "654321",
    });
    expect(pushMock).toHaveBeenCalledWith("/auth/new-password");
  });

  it("validates and submits new password", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ success: true, redirect: "/auth/login?reset=1" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<NewPasswordPage />);

    expect(
      screen.getByRole("heading", { name: "Choose a new password" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("New password"), "UpdatedPass123!");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "UpdatedPass123!",
    );
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/recovery/password");
    expect(JSON.parse(opts.body)).toEqual({
      password: "UpdatedPass123!",
      passwordConfirm: "UpdatedPass123!",
    });
    expect(pushMock).toHaveBeenCalledWith("/auth/login?reset=1");
  });
});
