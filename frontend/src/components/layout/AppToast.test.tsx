import { screen } from "@testing-library/react";
import { AppToast } from "./AppToast";
import { renderWithStore } from "../../test/renderWithStore";

describe("AppToast", () => {
  it("renders toast message from shell slice", () => {
    renderWithStore(<AppToast />, {
      store: {
        shell: {
          toast: { message: "Download complete", type: "success" },
          toastKey: 7,
        },
      },
    });

    expect(screen.getByText("Download complete")).toBeInTheDocument();
  });

  it("renders nothing when toast is null", () => {
    const { container } = renderWithStore(<AppToast />, {
      store: { shell: { toast: null } },
    });

    expect(container).toBeEmptyDOMElement();
  });
});
