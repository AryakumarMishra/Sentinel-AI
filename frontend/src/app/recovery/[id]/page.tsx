'use client';

import { useEffect, useState, use } from 'react';
import { api, RecoveryRecord } from '../../../lib/api';
import Link from 'next/link';

export default function RecoveryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [record, setRecord] = useState<RecoveryRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actioning, setActioning] = useState<boolean>(false);

  useEffect(() => {
    async function fetchDetail() {
      try {
        const data = await api.getRecoveryDetail(id);
        setRecord(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    fetchDetail();
    // Poll updates every 2 seconds to render live timeline updates from our backend workers
    const interval = setInterval(fetchDetail, 2000);
    return () => clearInterval(interval);
  }, [id]);

  const handleDecision = async (approve: boolean) => {
    setActioning(true);
    try {
      await api.sendDecision(id, approve);
    } catch (err) {
      alert('Failed to transmit operator authorization change decision matrix.');
      console.error(err);
    } finally {
      setActioning(false);
    }
  };

  if (loading) {
    return <div className="h-64 flex items-center justify-center font-mono text-sm text-slate-500">Accessing secure node state tracker files...</div>;
  }

  if (!record) {
    return <div className="p-6 bg-rose-500/10 border rounded-lg text-rose-400 font-mono text-sm">Error: Secure tracking session UUID index path missing.</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      
      {/* LEFT 2 COLUMNS: Timeline, Analysis & Review Panel */}
      <div className="lg:col-span-2 space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/" className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-400 hover:text-white transition-colors">
            ← Registry
          </Link>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Inspection Path: {record.project_name}</h2>
            <p className="text-xs font-mono text-slate-400 mt-0.5">Pipeline Cluster Hook: #{record.pipeline_id}</p>
          </div>
        </div>

        {/* HUMAN REVIEW INTERFACE PANEL (Only rendered if state matches) */}
        {record.status === 'AWAITING_APPROVAL' && record.proposed_fix && (
          <div className="border border-amber-500/30 bg-amber-500/5 rounded-xl p-6 backdrop-blur-md space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-lg animate-pulse">⚠️</span>
              <div>
                <h3 className="text-sm font-bold text-amber-400">Security Gate: Human Approval Required</h3>
                <p className="text-xs text-slate-400 mt-0.5">Gemini has generated a code solution. Review the code adjustments before pushing to GitLab.</p>
              </div>
            </div>

            <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 font-mono text-xs space-y-3">
              <div>
                <span className="text-slate-500 font-semibold uppercase tracking-wider text-[10px]">Target File Path:</span>
                <p className="text-cyan-400 font-bold mt-0.5">{record.proposed_fix.file_path}</p>
              </div>
              <div>
                <span className="text-slate-500 font-semibold uppercase tracking-wider text-[10px]">AI Root-Cause Diagnosis:</span>
                <p className="text-slate-300 mt-0.5 leading-relaxed">{record.proposed_fix.explanation}</p>
              </div>
              <div>
                <span className="text-slate-500 font-semibold uppercase tracking-wider text-[10px]">Proposed Code Modification Patch:</span>
                <pre className="mt-1.5 p-3 bg-slate-900/60 rounded-md border border-slate-800 text-emerald-400 overflow-x-auto leading-relaxed">
                  <code>{record.proposed_fix.content}</code>
                </pre>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <button 
                onClick={() => handleDecision(true)} 
                disabled={actioning}
                className="flex-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs py-2.5 transition-all shadow-md shadow-emerald-500/10 cursor-pointer"
              >
                {actioning ? 'Deploying Changes...' : '✔ Approve & Create Git Branch'}
              </button>
              <button 
                onClick={() => handleDecision(false)} 
                disabled={actioning}
                className="rounded-lg bg-slate-800 hover:bg-rose-500/20 hover:text-rose-400 border border-slate-700 text-slate-300 font-bold text-xs px-4 py-2.5 transition-all cursor-pointer"
              >
                Discard Patch
              </button>
            </div>
          </div>
        )}

        {/* COMPLETED REPAIR VIEWER (Rendered if the patch was already approved) */}
        {record.approved_by_human && record.proposed_fix && (
          <div className="border border-slate-800 bg-slate-900/10 rounded-xl p-6 space-y-3 font-mono text-xs">
            <h3 className="text-sm font-bold text-emerald-400 font-sans">✓ Applied Remediation Blueprint</h3>
            <p className="text-slate-400"><span className="text-slate-600">File:</span> {record.proposed_fix.file_path}</p>
            <pre className="p-3 bg-slate-950 rounded-md border border-slate-800 text-slate-400 overflow-x-auto">
              <code>{record.proposed_fix.content}</code>
            </pre>
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Real-time Timeline Status Window */}
      <div className="border border-slate-800 bg-slate-900/20 rounded-xl p-6 backdrop-blur-md h-fit space-y-4">
        <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">Live Telemetry Process Track</h3>
        
        {record.steps.length === 0 ? (
          <p className="text-xs font-mono text-slate-600">Bootstrapping pipeline worker nodes...</p>
        ) : (
          <div className="relative border-l border-slate-800 ml-2 pl-6 space-y-6 font-mono text-xs">
            {record.steps.map((step, idx) => (
              <div key={idx} className="relative group">
                {/* Node Status Visual Marker Anchor */}
                <div className={`absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full border bg-slate-950 flex items-center justify-center text-[7px] font-bold
                  ${step.status === 'SUCCESS' ? 'border-emerald-500 text-emerald-400 shadow-md shadow-emerald-500/20' : ''}
                  ${step.status === 'FAILED' ? 'border-rose-500 text-rose-400' : ''}
                  ${step.status === 'IN_PROGRESS' ? 'border-cyan-500 text-cyan-400 animate-pulse' : ''}
                `}>
                  {step.status === 'SUCCESS' ? '✓' : step.status === 'FAILED' ? '✕' : '●'}
                </div>
                
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-slate-200">{step.step.replace('_', ' ')}</span>
                    <span className="text-[10px] text-slate-600">
                      {new Date(step.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  {step.details && <p className="text-slate-400 mt-1 font-sans text-xs leading-relaxed">{step.details}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
