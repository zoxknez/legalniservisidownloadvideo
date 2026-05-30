import { createContext, useContext, type ReactNode } from "react";

export function createSliceContext<T>(displayName: string) {
  const Context = createContext<T | null>(null);
  Context.displayName = `${displayName}Context`;

  function Provider({ value, children }: { value: T; children: ReactNode }) {
    return <Context.Provider value={value}>{children}</Context.Provider>;
  }
  Provider.displayName = `${displayName}Provider`;

  function useSlice(): T {
    const value = useContext(Context);
    if (value === null) {
      throw new Error(`${displayName} slice must be used within AppProvider`);
    }
    return value;
  }

  return { Context, Provider, useSlice };
}
