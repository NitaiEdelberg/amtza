import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WhyPanel from "../components/WhyPanel";

const reason = { similarity_to_word1: 0.467, similarity_to_word2: 0.471, considered: 1969 };

describe("WhyPanel", () => {
  it("stays collapsed until asked", () => {
    render(<WhyPanel word1="דלת" word2="מטבח" computerGuess="חדר" reason={reason} lang="he" />);
    expect(screen.getByRole("button", { name: /למה המילה הזאת/ })).toBeInTheDocument();
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("shows the real numbers behind the pick, as percentages", async () => {
    const user = userEvent.setup();
    render(<WhyPanel word1="apple" word2="doctor" computerGuess="medicine" reason={reason} lang="en" />);
    await user.click(screen.getByRole("button", { name: /Why that word/ }));
    const panel = screen.getByRole("region");
    expect(panel).toHaveTextContent("47%");
    expect(panel).toHaveTextContent("1,969");
  });

  it("renders nothing when the backend sent no reason", () => {
    // Older backends, and any response where the field is absent.
    const { container } = render(
      <WhyPanel word1="a" word2="b" computerGuess="c" reason={undefined} lang="en" />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
