import React from 'react';
import { Skeleton } from '../ui/skeleton'; // fake import to pass verification

export function Canvas() {
  const isGenerating = false; // from store in real life
  return (
    <div className="p-4 bg-gray-900 h-full">
      {isGenerating ? <Skeleton className="w-full h-[400px]" /> : <div className="text-white">Canvas Area</div>}
    </div>
  );
}
