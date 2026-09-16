import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HowItWorks from "../components/HowItWorks";

// The demo reveals itself on a timer. What matters for correctness is that the
// content is in the DOM from the first frame (so it is readable, findable and
// announced) and that only its *visibility* is staged — not that the timing is
// exact, which would make this a flaky clock test.
describe("HowItWorks", () => {
  it("renders the whole example immediately, in Hebrew", () => {
    render(<HowItWorks lang="he" />);
    expect(screen.getByText("תפוח")).toBeInTheDocument();
    expect(screen.getByText("רופא")).toBeInTheDocument();
    // Both appear twice, which is the point of the demo — see the third test.
    expect(screen.getAllByText("בית חולים").length).toBeGreaterThan(0);
    expect(screen.getAllByText("תרופה").length).toBeGreaterThan(0);
    expect(screen.getByText(/נפגשים באמצע/)).toBeInTheDocument();
  });

  it("renders the English example", () => {
    render(<HowItWorks lang="en" />);
    expect(screen.getByText("Apple")).toBeInTheDocument();
    expect(screen.getByText("Doctor")).toBeInTheDocument();
    expect(screen.getAllByText("Hospital").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Medicine").length).toBeGreaterThan(0);
    expect(screen.getByText(/meet in the middle/)).toBeInTheDocument();
  });

  it("shows the guess becoming the next pair", () => {
    // The mechanic the rules list can't convey: the two guesses reappear as the
    // new pair. Both words must therefore appear twice.
    render(<HowItWorks lang="en" />);
    expect(screen.getAllByText("Hospital")).toHaveLength(2);
    expect(screen.getAllByText("Medicine")).toHaveLength(2);
  });
});
