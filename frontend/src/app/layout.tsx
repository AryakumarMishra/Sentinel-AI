import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

import {
  Bot,
  LayoutDashboard,
  Zap,
} from 'lucide-react';

export const metadata: Metadata = {
  title: 'Sentinel AI | Self-Healing DevOps Agent Engine',
  description: 'Powered by Gemini & Google Agent Development Kit',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark bg-slate-950 text-slate-100">
      <body className="flex min-h-screen font-sans antialiased selection:bg-cyan-500 selection:text-slate-900">

        {/* Fixed Left Navigation Panel */}
        <aside className="fixed inset-y-0 left-0 w-64 border-r border-slate-800 bg-slate-900/50 p-6 backdrop-blur-xl">
          <div className="flex flex-col h-full justify-between">

            <div>
              {/* Logo */}
              <div className="flex items-center gap-3 px-2 py-4 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/20">
                  <Bot className="h-5 w-5 text-cyan-400" />
                </div>

                <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-indigo-400 bg-clip-text text-transparent tracking-tight">
                  Sentinel AI
                </h1>
              </div>

              {/* Navigation */}
              <nav className="space-y-1">

                <Link
                  href="/"
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-slate-300 hover:bg-slate-800 hover:text-white group"
                >
                  <LayoutDashboard className="h-4 w-4 text-slate-400 group-hover:text-cyan-400 transition-colors" />
                  Dashboard Index
                </Link>

                <Link
                  href="/trigger"
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-slate-300 hover:bg-slate-800 hover:text-white group"
                >
                  <Zap className="h-4 w-4 text-slate-400 group-hover:text-cyan-400 transition-colors" />
                  Manual Trigger
                </Link>

              </nav>
            </div>

            {/* Footer */}
            <div className="border-t border-slate-800 pt-4 px-2">
              <p className="text-[11px] text-slate-500 font-mono tracking-wider uppercase">
                Google Rapid Agent Hackathon
              </p>

              <p className="text-xs text-slate-400 font-semibold mt-1">
                GitLab Partner Track
              </p>
            </div>

          </div>
        </aside>

        {/* Main Application Grid Area Container */}
        <main className="pl-64 flex-1 flex flex-col min-h-screen">

          <header className="h-16 border-b border-slate-800 bg-slate-900/20 px-8 flex items-center justify-between sticky top-0 backdrop-blur-md z-10">

            <div className="text-xs font-mono text-slate-400">
              System Nodes Status:{' '}
              <span className="text-emerald-400 font-bold animate-pulse">
                ● ONLINE
              </span>
            </div>

            <div className="px-3 py-1 rounded-full border border-slate-700 bg-slate-800 text-[11px] font-mono text-slate-300">
              Engine: gemini-2.5-flash-lite
            </div>

          </header>

          <div className="p-8 flex-1 max-w-7xl w-full mx-auto">
            {children}
          </div>

        </main>

      </body>
    </html>
  );
}