'use client';
import React, { useEffect, useRef } from 'react';
import { useAppStore } from '../../store/useAppStore';

export function Canvas() {
  const { isGenerating, setIsGenerating, postContent, appendPostContent } = useAppStore();
  const generationStarted = useRef(false);

  useEffect(() => {
    let active = true;

    const startStreaming = async () => {
      if (!isGenerating || generationStarted.current) return;
      generationStarted.current = true;

      try {
        // We simulate calling the API. In a real SSE scenario via POST,
        // we'd use fetch and read the ReadableStream from the response body.
        const response = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            post_type: 'promotional_article',
            topic: 'New Feature Launch'
          }),
        });

        if (!response.ok) {
          throw new Error('Network response was not ok');
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          while (active) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });

            // Basic SSE parsing (assuming data: ... format from backend)
            const lines = chunk.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.chunk) {
                    appendPostContent(data.chunk);
                  }
                } catch (_e) {
                  // Fallback for raw text chunks
                  const text = line.slice(6);
                  if (text && text !== '[DONE]') {
                    appendPostContent(text);
                  }
                }
              } else if (line && !line.startsWith(':') && !line.startsWith('event:')) {
                // If it's just raw text not formatted as strict SSE
                appendPostContent(line);
              }
            }
          }
        }
      } catch (error) {
        console.error('Streaming error:', error);
      } finally {
        if (active) {
          setIsGenerating(false);
          generationStarted.current = false;
        }
      }
    };

    if (isGenerating) {
      startStreaming();
    }

    return () => {
      active = false;
      if (isGenerating) {
        generationStarted.current = false;
      }
    };
  }, [isGenerating, appendPostContent, setIsGenerating]);

  return (
    <div className="p-4 bg-[#0E0E0E] h-full overflow-y-auto">
      {isGenerating && !postContent ? (
        <div className="animate-pulse flex flex-col gap-4 w-full p-4">
          <div className="h-6 bg-[#1A1A1A] rounded w-3/4"></div>
          <div className="h-4 bg-[#1A1A1A] rounded w-full"></div>
          <div className="h-4 bg-[#1A1A1A] rounded w-5/6"></div>
          <div className="h-[200px] bg-[#1A1A1A] rounded w-full mt-4"></div>
        </div>
      ) : (
        <div className="text-white whitespace-pre-wrap font-sans">
          {postContent || <div className="text-gray-500 italic">Canvas Area - Generate a post to see results here.</div>}
        </div>
      )}
    </div>
  );
}
