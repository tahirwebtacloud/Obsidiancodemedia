import { create } from 'zustand';

interface AppState {
  activeTab: string;
  setActiveTab: (tab: string) => void;

  // Studio Form State (to be expanded later)
  studioState: Record<string, any>;
  setStudioState: (state: Record<string, any>) => void;

  // Brand Identity Configuration
  brandIdentity: Record<string, any>;
  setBrandIdentity: (config: Record<string, any>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: '/studio',
  setActiveTab: (tab) => set({ activeTab: tab }),

  studioState: {},
  setStudioState: (state) => set((prev) => ({ studioState: { ...prev.studioState, ...state } })),

  brandIdentity: {},
  setBrandIdentity: (config) => set((prev) => ({ brandIdentity: { ...prev.brandIdentity, ...config } })),
}));
