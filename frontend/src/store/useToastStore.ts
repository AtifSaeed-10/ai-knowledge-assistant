import { create } from "zustand";

export type ToastVariant = "error" | "success" | "info";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id"> & { id?: string }) => string;
  dismiss: (id: string) => void;
}

const DURATION: Record<ToastVariant, number> = {
  error: 8000,
  success: 3500,
  info: 5000,
};

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],

  push: ({ id, ...toast }) => {
    const toastId = id || `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    set((state) => ({
      // Replacing by id keeps repeated failures (e.g. polling) from stacking up.
      toasts: [...state.toasts.filter((item) => item.id !== toastId), { ...toast, id: toastId }],
    }));

    if (typeof window !== "undefined") {
      window.setTimeout(() => get().dismiss(toastId), DURATION[toast.variant]);
    }

    return toastId;
  },

  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}));

/** Convenience helper for use outside React components (stores, api callers). */
export const notify = {
  error: (title: string, description?: string, id?: string) =>
    useToastStore.getState().push({ title, description, variant: "error", id }),
  success: (title: string, description?: string, id?: string) =>
    useToastStore.getState().push({ title, description, variant: "success", id }),
  info: (title: string, description?: string, id?: string) =>
    useToastStore.getState().push({ title, description, variant: "info", id }),
};
