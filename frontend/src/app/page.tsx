'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, RecoveryRecord } from '../lib/api';

export default function DashboardPage() {
  const [recoveries, setRecoveries] = useState<RecoveryRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Poll our FastAPI state file directory every 3 seconds for live timeline updates
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    async function fetchData() {
      try {
        const data = await api.getRecoveries();
        setRecoveries(data.sort((a, b) => b.start_time.localeCompare(a.start_time)));
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    function startPolling() {
      if (!intervalId) {
        fetchData(); // Run immediately on focus/mount
        intervalId = setInterval(fetchData, 10000); // 10-second smart polling interval
      }
    }

    function stopPolling() {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    }

    // Handle visibility changes (tab switching)
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    // Initial active state setup
    if (!document.hidden) {
      startPolling();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Clean up completely on unmount
    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // Simple clean formatting utility function for ISO timestamps
  const formatTime = (isoStr: string) => {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // Maps backend states to clean colored Tailwind CSS layouts
  const getBadgeStyle = (status: string) => {
    if (status.includes('SUCCESS')) return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
    if (status.includes('FAILED') || status.includes('REJECTED')) return 'bg-rose-500/10 border-rose-500/30 text-rose-400';
    if (status === 'AWAITING_APPROVAL') return 'bg-amber-500/10 border-amber-500/30 text-amber-400 border animate-pulse';
    return 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400';
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center font-mono text-sm text-slate-500">
        Loading core tracking registry index...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Remediation Node Registry</h2>
        <p className="text-sm text-slate-400 mt-1">Live tracking interface capturing GitLab CI failure telemetry streams.</p>
      </div>

      {recoveries.length === 0 ? (
        <div className="border border-dashed border-slate-800 rounded-xl p-12 text-center text-slate-500 font-mono text-sm">
          No automated recovery instances logged yet. Trigger an error payload to begin.
        </div>
      ) : (
        <div className="border border-slate-800 rounded-xl bg-slate-900/20 overflow-hidden backdrop-blur-md">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 font-mono text-xs text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4">Timestamp</th>
                  <th className="px-6 py-4">Repository Node</th>
                  <th className="px-6 py-4">Pipeline Ref</th>
                  <th className="px-6 py-4">Execution State</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm font-mono">
                {recoveries.map((run) => (
                  <tr key={run.recovery_id} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-6 py-4 text-slate-400">{formatTime(run.start_time)}</td>
                    <td className="px-6 py-4 font-bold text-slate-200">{run.project_name}</td>
                    <td className="px-6 py-4 text-slate-400">#{run.pipeline_id}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide border ${getBadgeStyle(run.status)}`}>
                        {run.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link 
                        href={`/recovery/${run.recovery_id}`} 
                        className="inline-flex items-center justify-center rounded-lg px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 transition-all border border-slate-700 text-slate-300"
                      >
                        Inspect Node →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
