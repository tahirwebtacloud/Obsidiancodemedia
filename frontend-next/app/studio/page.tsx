import React from 'react';
import { StudioForm } from '../../components/studio/StudioForm';
import { Canvas } from '../../components/studio/Canvas';

export default function StudioPage() {
  return (
    <div className="flex flex-col lg:flex-row h-screen">
      <div className="lg:w-1/2 w-full"><StudioForm /></div>
      <div className="lg:w-1/2 hidden lg:block"><Canvas /></div>
    </div>
  );
}
