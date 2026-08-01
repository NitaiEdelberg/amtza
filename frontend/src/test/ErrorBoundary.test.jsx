import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary";

function Boom() {
  throw new Error("kaboom");
}

beforeEach(() => {
  // React logs the caught error; that's expected here and would only add noise.
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("renders children when nothing goes wrong", () => {
    render(
      <ErrorBoundary>
        <p>the game</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("the game")).toBeInTheDocument();
  });

  it("shows a recovery screen instead of a blank page when a child throws", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reload/ })).toBeInTheDocument();
  });

  it("uses Hebrew copy when asked", () => {
    render(
      <ErrorBoundary language="he">
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByText(/משהו השתבש/)).toBeInTheDocument();
  });

  it("logs the failure so a deployed build can be debugged", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    expect(console.error).toHaveBeenCalled();
  });
});
