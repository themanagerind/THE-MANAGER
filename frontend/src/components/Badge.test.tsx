import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/Badge";

describe("Badge", () => {
  it("renders known statuses without crashing", () => {
    render(<Badge status="PAID">PAID</Badge>);
    expect(screen.getByText("PAID")).toBeInTheDocument();
  });

  it("falls back to neutral tone for a status not in the map, instead of throwing", () => {
    // Guards against a future backend enum value the frontend hasn't been
    // updated for yet (docs/API_CONTRACT.md: "closed sets" — but this is
    // the safety net for the gap between a backend release and a frontend one).
    expect(() => render(<Badge status="SOME_FUTURE_STATUS">Unknown</Badge>)).not.toThrow();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("renders with no status at all", () => {
    render(<Badge>No status</Badge>);
    expect(screen.getByText("No status")).toBeInTheDocument();
  });
});
