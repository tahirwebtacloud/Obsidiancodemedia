import { create } from 'zustand';

interface AppState {
  activeTab: string;
  setActiveTab: (tab: string) => void;

  // Studio Form State
  studioState: Record<string, unknown>;
  setStudioState: (state: Record<string, unknown>) => void;

  // Studio Execution State
  isGenerating: boolean;
  setIsGenerating: (generating: boolean) => void;
  postContent: string;
  setPostContent: (content: string) => void;
  appendPostContent: (chunk: string) => void;

  // Mobile View State
  showCanvasMobile: boolean;
  setShowCanvasMobile: (show: boolean) => void;

  // Brand Identity Configuration
  brandIdentity: Record<string, unknown>;
  setBrandIdentity: (config: Record<string, unknown>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: '/studio',
  setActiveTab: (tab) => set({ activeTab: tab }),

  studioState: {},
  setStudioState: (state) => set((prev) => ({ studioState: { ...prev.studioState, ...state } })),

  isGenerating: false,
  setIsGenerating: (generating) => set({ isGenerating: generating }),

  postContent: '',
  setPostContent: (content) => set({ postContent: content }),
  appendPostContent: (chunk) => set((prev) => ({ postContent: prev.postContent + chunk })),

  showCanvasMobile: false,
  setShowCanvasMobile: (show) => set({ showCanvasMobile: show }),

  brandIdentity: {},
  setBrandIdentity: (config) => set((prev) => ({ brandIdentity: { ...prev.brandIdentity, ...config } })),
}));
