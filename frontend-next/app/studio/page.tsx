'use client';
import React from 'react';
import { StudioForm } from '../../components/studio/StudioForm';
import { Canvas } from '../../components/studio/Canvas';
import { useAppStore } from '../../store/useAppStore';

export default function StudioPage() {
  const { showCanvasMobile, setShowCanvasMobile } = useAppStore();

  return (
    <div className="flex flex-col lg:flex-row h-screen">
      <div className={`lg:w-1/2 w-full ${showCanvasMobile ? 'hidden lg:block' : 'block'}`}>
        <StudioForm />
      </div>

      <div className={`lg:w-1/2 w-full ${showCanvasMobile ? 'block' : 'hidden lg:block'}`}>
        {/* Mobile Toggle Back Button */}
        {showCanvasMobile && (
          <div className="lg:hidden p-4 bg-[#0E0E0E] text-white flex items-center">
            <button
              onClick={() => setShowCanvasMobile(false)}
              className="text-[#F9C74F] font-bold flex items-center gap-2"
            >
              <span>←</span> Back to Editor
            </button>
          </div>
        )}
        <Canvas />
      </div>
    </div>
  );
}
