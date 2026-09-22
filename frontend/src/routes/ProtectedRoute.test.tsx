import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

const mockUseAuth = vi.fn();
vi.mock("@/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

import { ProtectedRoute } from "@/routes/ProtectedRoute";

function renderAt(path: string, allow?: ("ADMIN" | "RESIDENT")[]) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/" element={<div>Role home</div>} />
        <Route element={<ProtectedRoute allow={allow as never} />}>
          <Route path={path === "/login" ? "/protected" : path} element={<div>Protected content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("shows a loading spinner while bootstrapping (fix #3 — never trusts localStorage alone)", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, activeRole: "RESIDENT", isBootstrapping: true });
    renderAt("/protected");
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("redirects to /login when not authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, activeRole: null, isBootstrapping: false });
    renderAt("/protected");
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("renders protected content when authenticated and role allowed", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, activeRole: "RESIDENT", isBootstrapping: false });
    renderAt("/protected", ["RESIDENT"]);
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects home when the active role isn't in the allow-list (e.g. Admin viewing a Resident-only route)", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, activeRole: "ADMIN", isBootstrapping: false });
    renderAt("/protected", ["RESIDENT"]);
    expect(screen.getByText("Role home")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });
});
