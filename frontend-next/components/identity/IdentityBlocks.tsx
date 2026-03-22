'use client';

import React from 'react';

interface IdentityBlockProps {
  title: string;
  data: Record<string, any>;
  onEdit?: (key: string, value: any) => void;
}

export function IdentityBlocks({ title, data, onEdit }: IdentityBlockProps) {
  // Convert object to a structured string representation
  const renderValue = (key: string, val: any) => {
    if (typeof val === 'object' && val !== null) {
      return JSON.stringify(val, null, 2);
    }
    return String(val);
  };

  return (
    <div className="border border-[#333] bg-[#0E0E0E] text-[#e0e0e0] font-mono rounded-md overflow-hidden shadow-sm mb-6">
      <div className="flex items-center justify-between border-b border-[#333] px-4 py-2 bg-[#1a1a1a]">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-[#F9C74F]"></div>
          <span className="text-sm font-semibold tracking-wide text-[#F9C74F]">
            {title}
          </span>
        </div>
        <span className="text-xs text-gray-500">config.json</span>
      </div>

      <div className="p-4 text-sm leading-relaxed overflow-x-auto">
        <span className="text-[#F9C74F]">{"{"}</span>
        <div className="pl-4">
          {Object.entries(data).length === 0 ? (
            <div className="text-gray-500 italic">// No configuration set</div>
          ) : (
            Object.entries(data).map(([key, value], index, arr) => (
              <div key={key} className="my-1 group relative">
                <span className="text-[#9cdcfe]">"{key}"</span>
                <span className="text-gray-400">: </span>
                {typeof value === 'string' ? (
                  <span className="text-[#ce9178]">
                    "{value}"
                  </span>
                ) : (
                  <span className="text-[#b5cea8]">
                    {renderValue(key, value)}
                  </span>
                )}
                {index < arr.length - 1 && <span className="text-gray-400">,</span>}

                {onEdit && (
                  <button
                    onClick={() => {
                      const newVal = prompt(`Edit ${key}`, typeof value === 'string' ? value : renderValue(key, value));
                      if (newVal !== null) {
                        try {
                          // Try parsing as JSON first if it looks like it might be an object/array/boolean
                          const parsed = (newVal.startsWith('{') || newVal.startsWith('[') || newVal === 'true' || newVal === 'false')
                            ? JSON.parse(newVal)
                            : newVal;
                          onEdit(key, parsed);
                        } catch (e) {
                          onEdit(key, newVal);
                        }
                      }
                    }}
                    className="absolute right-0 top-0 opacity-0 group-hover:opacity-100 px-2 py-0.5 text-xs bg-[#333] hover:bg-[#444] text-[#F9C74F] rounded cursor-pointer transition-opacity"
                  >
                    Edit
                  </button>
                )}
              </div>
            ))
          )}
        </div>
        <span className="text-[#F9C74F]">{"}"}</span>
      </div>
    </div>
  );
}
