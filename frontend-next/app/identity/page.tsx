'use client';

import React, { useEffect, useState } from 'react';
import { IdentityBlocks } from '@/components/identity/IdentityBlocks';
import { useAppStore } from '@/store/useAppStore';

export default function IdentityManagerPage() {
  const { brandIdentity, setBrandIdentity } = useAppStore();

  // Use local state to avoid hydration mismatch, and mock some data if empty
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    // Seed initial mock data if empty
    if (Object.keys(brandIdentity).length === 0) {
      setBrandIdentity({
        persona: {
          role: "AI Automations Expert",
          tone: "Direct, technical, and slightly contrarian",
          expertise_areas: ["AI Workflows", "GTM Automation", "Growth Engineering"]
        },
        brand_knowledge: {
          company_name: "Obsidian Logic",
          core_offer: "Bespoke AI Architecture",
          target_audience: "B2B SaaS Founders, VP Eng"
        },
        output_directives: {
          formatting: "Strictly avoid AI buzzwords (e.g., 'synergy', 'transformative'). Use short paragraphs.",
          hooks: "Always start with a counter-intuitive truth or hard metric.",
          ctas: "Drive to substack newsletter or direct consultation booking."
        }
      });
    }
  }, []);

  if (!mounted) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-[#F9C74F] font-mono">Loading identity configuration...</div>
      </div>
    );
  }

  const handleUpdate = (section: string, key: string, value: any) => {
    const currentSection = brandIdentity[section] || {};
    setBrandIdentity({
      [section]: {
        ...currentSection,
        [key]: value
      }
    });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div className="border-b border-[#333] pb-4 mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Brand Identity Manager</h1>
        <p className="text-gray-400 font-mono text-sm">
          // Centralized playbook constraints guiding generation logic
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-white">Persona</h2>
            <p className="text-sm text-gray-500">Defines the voice, tone, and character of the generated content.</p>
          </div>
          <IdentityBlocks
            title="Persona Constraints"
            data={brandIdentity.persona || {}}
            onEdit={(key, val) => handleUpdate('persona', key, val)}
          />
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-white">Brand Knowledge</h2>
            <p className="text-sm text-gray-500">Core facts, offerings, and positioning specific to the company.</p>
          </div>
          <IdentityBlocks
            title="Brand Knowledge Map"
            data={brandIdentity.brand_knowledge || {}}
            onEdit={(key, val) => handleUpdate('brand_knowledge', key, val)}
          />
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-white">Output Directives</h2>
            <p className="text-sm text-gray-500">Strict formatting rules, hook patterns, and required call-to-actions.</p>
          </div>
          <IdentityBlocks
            title="Execution Directives"
            data={brandIdentity.output_directives || {}}
            onEdit={(key, val) => handleUpdate('output_directives', key, val)}
          />
        </section>
      </div>
    </div>
  );
}
