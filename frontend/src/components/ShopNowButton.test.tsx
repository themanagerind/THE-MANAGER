import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/showcasePrefill", () => ({
  showcasePrefillApi: { create: vi.fn() },
}));

import { showcasePrefillApi } from "@/api/showcasePrefill";
import { ShopNowButton } from "@/components/ShopNowButton";

describe("ShopNowButton", () => {
  beforeEach(() => {
    vi.mocked(showcasePrefillApi.create).mockReset();
    // jsdom doesn't implement real navigation — replace location with a
    // plain writable stub so `window.location.href = ...` is just a
    // property set we can assert on, not an unimplemented-navigation error.
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: "" },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders nothing when Showcase has no configured domain yet", () => {
    vi.stubEnv("VITE_SHOWCASE_BASE_URL", "");
    const { container } = render(<ShopNowButton />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the DPDP consent notice before issuing a token, and does not call the API until confirmed", async () => {
    vi.stubEnv("VITE_SHOWCASE_BASE_URL", "https://showcase.example.com");
    const user = userEvent.setup();
    render(<ShopNowButton />);

    await user.click(screen.getByRole("button", { name: "Shop Now" }));
    expect(screen.getByText(/will be shared with Showcase/)).toBeInTheDocument();
    expect(showcasePrefillApi.create).not.toHaveBeenCalled();
  });

  it("on confirm, issues a token and redirects to Showcase with it", async () => {
    vi.stubEnv("VITE_SHOWCASE_BASE_URL", "https://showcase.example.com");
    vi.mocked(showcasePrefillApi.create).mockResolvedValue({
      data: { token: "abc123", expires_at: "2026-01-01T00:05:00Z" },
    } as never);
    const user = userEvent.setup();
    render(<ShopNowButton />);

    await user.click(screen.getByRole("button", { name: "Shop Now" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(showcasePrefillApi.create).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("https://showcase.example.com/signup?prefill=abc123");
  });

  it("shows a retry-friendly error instead of redirecting if token issuance fails", async () => {
    vi.stubEnv("VITE_SHOWCASE_BASE_URL", "https://showcase.example.com");
    vi.mocked(showcasePrefillApi.create).mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(<ShopNowButton />);

    await user.click(screen.getByRole("button", { name: "Shop Now" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByText(/Couldn't start this/)).toBeInTheDocument();
    expect(window.location.href).toBe("");
  });
});
