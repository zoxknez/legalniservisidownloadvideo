import { render, screen } from "@testing-library/react";
import { AboutTab } from "./AboutTab";

describe("AboutTab", () => {
  it("renders app title and creator section", () => {
    render(<AboutTab />);

    expect(screen.getByRole("heading", { name: /O Aplikaciji/i })).toBeInTheDocument();
    expect(screen.getByText("o0o0o0o")).toBeInTheDocument();
    expect(screen.getByText(/Glavni Programer/i)).toBeInTheDocument();
  });
});
