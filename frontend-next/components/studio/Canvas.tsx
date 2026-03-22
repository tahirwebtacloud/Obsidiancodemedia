import React from 'react';

export function Canvas() {
  const isGenerating = false; // from store in real life
  return (
    <div className="p-4 bg-gray-900 h-full">
      {isGenerating ? <div className="animate-pulse bg-gray-800 w-full h-[400px] rounded-md" /> : <div className="text-white">Canvas Area</div>}
    </div>
  );
}
