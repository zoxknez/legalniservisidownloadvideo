import type { ToastType } from "../types/app";

export type ShowToastFn = (message: string, type?: ToastType) => void;
