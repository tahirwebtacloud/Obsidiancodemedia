'use client';
import React from 'react';
import { useAppStore } from '../../store/useAppStore';

export function StudioForm() {
  const { setStudioState, setIsGenerating, setShowCanvasMobile, setPostContent } = useAppStore();

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    setStudioState({ isGenerating: true });
    setIsGenerating(true);
    setPostContent(''); // Clear previous
    setShowCanvasMobile(true); // Switch to canvas on mobile
  };

  return (
    <div className="p-4 bg-[#0E0E0E] text-[#F9C74F] h-full">
      <form onSubmit={handleGenerate} className="flex flex-col gap-4">
        <input className="bg-black text-white p-2 rounded" type="text" placeholder="Prompt..." />
        <button type="submit" className="bg-[#F9C74F] text-black font-bold p-2 rounded w-max">
          Generate
        </button>
      </form>
    </div>
  );
}
