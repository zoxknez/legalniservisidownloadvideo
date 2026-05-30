import { render, screen } from "@testing-library/react";
import { createSliceContext } from "./createSliceContext";

describe("createSliceContext", () => {
  it("throws when hook is used outside provider", () => {
    const { useSlice } = createSliceContext<{ value: string }>("Test");

    expect(() => render(<Reader useSlice={useSlice} />)).toThrow(
      "Test slice must be used within AppProvider",
    );
  });

  it("provides slice value to descendants", () => {
    const { Provider, useSlice } = createSliceContext<{ value: string }>("Test");

    render(
      <Provider value={{ value: "hello" }}>
        <Reader useSlice={useSlice} />
      </Provider>,
    );

    expect(screen.getByTestId("slice-value")).toHaveTextContent("hello");
  });
});

function Reader({ useSlice }: { useSlice: () => { value: string } }) {
  const slice = useSlice();
  return <span data-testid="slice-value">{slice.value}</span>;
}
