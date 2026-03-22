'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAppStore } from '../store/useAppStore';
import { useEffect } from 'react';

const navItems = [
  { name: 'Studio', href: '/studio' },
  { name: 'Intelligence', href: '/intelligence' },
  { name: 'Evolution', href: '/evolution' },
  { name: 'Identity', href: '/identity' },
];

export function Navigation() {
  const pathname = usePathname();
  const setActiveTab = useAppStore((state) => state.setActiveTab);

  useEffect(() => {
    setActiveTab(pathname);
  }, [pathname, setActiveTab]);

  return (
    <nav className="flex-none w-full md:w-64 bg-sidebar border-b md:border-b-0 md:border-r border-sidebar-border p-4 flex flex-row md:flex-col gap-2 overflow-x-auto overflow-y-hidden md:overflow-y-auto">
      <div className="hidden md:block mb-8">
        <h1 className="text-xl font-bold text-foreground tracking-tighter uppercase border-b-2 border-primary pb-2 inline-block">
          Obsidian Logic
        </h1>
      </div>
      <ul className="flex flex-row md:flex-col gap-2 w-full">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <li key={item.name} className="flex-shrink-0">
              <Link
                href={item.href}
                className={`block px-4 py-3 text-sm md:text-base font-semibold transition-colors duration-200 border-l-4 ${
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground border-primary'
                    : 'text-muted-foreground border-transparent hover:bg-sidebar-accent/50 hover:text-foreground hover:border-muted-foreground'
                }`}
              >
                {item.name}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
