import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { ComposeSliceProviders } from "../context/ComposeSliceProviders";
import type { AppStore } from "../context/appStore";
import { createTestStore, type TestStoreOverrides } from "./createTestStore";

export function StoreWrapper({
  store,
  children,
}: {
  store: AppStore;
  children: ReactNode;
}) {
  return <ComposeSliceProviders store={store}>{children}</ComposeSliceProviders>;
}

export function renderWithStore(
  ui: ReactElement,
  {
    store: storeOverrides,
    ...renderOptions
  }: Omit<RenderOptions, "wrapper"> & { store?: TestStoreOverrides } = {},
) {
  const store = createTestStore(storeOverrides);
  return render(ui, {
    wrapper: ({ children }) => <StoreWrapper store={store}>{children}</StoreWrapper>,
    ...renderOptions,
  });
}

export function wrapperWithStore(storeOverrides?: TestStoreOverrides) {
  const store = createTestStore(storeOverrides);
  return function Wrapper({ children }: { children: ReactNode }) {
    return <StoreWrapper store={store}>{children}</StoreWrapper>;
  };
}
