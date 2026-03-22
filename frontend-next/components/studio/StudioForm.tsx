import React from 'react';
import { useAppStore } from '../../store/useAppStore';

export function StudioForm() {
  const { setStudioState } = useAppStore();
  return (
    <div className="p-4 bg-[#0E0E0E] text-[#F9C74F]">
      <form onSubmit={(e) => { e.preventDefault(); setStudioState({ isGenerating: true }); }}>
        <input className="bg-black text-white" type="text" placeholder="Prompt..." />
        <button type="submit" className="bg-[#F9C74F] text-black p-2 rounded">Generate</button>
      </form>
    </div>
  );
}
