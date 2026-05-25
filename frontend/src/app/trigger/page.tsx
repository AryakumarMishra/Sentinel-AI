'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../../lib/api';

import {
  FolderGit2,
  GitBranch,
  Hash,
  TriangleAlert,
  Sparkles,
  Loader2,
} from 'lucide-react';

export default function TriggerPage() {
  const router = useRouter();

  const [projectPath, setProjectPath] = useState('');
  const [pipelineId, setPipelineId] = useState('');
  const [commitSha, setCommitSha] = useState('main');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!projectPath || !pipelineId) {
      setError(
        'Please provide a valid repository path and target pipeline ID.'
      );
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const result = await api.triggerManualHealing(
        encodeURIComponent(projectPath.trim()),
        Number(pipelineId.trim()),
        commitSha.trim()
      );

      router.push(`/recovery/${result.recovery_id}`);
    } catch (err: any) {
      setError(
        err.message ||
          'Failed to dispatch healing agent to repository.'
      );

      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">

      {/* Heading */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-400">
          <Sparkles className="h-3.5 w-3.5" />
          Autonomous DevOps Execution
        </div>

        <h2 className="text-3xl font-bold tracking-tight text-white">
          Manual Workload Dispatcher
        </h2>

        <p className="text-sm leading-relaxed text-slate-400 max-w-lg">
          Force an execution run on a target repository node for
          simulation testing and autonomous recovery analysis.
        </p>
      </div>

      {/* Form */}
      <form
        onSubmit={handleSubmit}
        className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-xl"
      >

        {/* Glow Accent */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-indigo-500/5 pointer-events-none" />

        <div className="relative space-y-5">

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-300">
              <TriangleAlert className="h-4 w-4 mt-0.5 shrink-0" />

              <div>
                <p className="font-medium">
                  Dispatch Failure
                </p>

                <p className="mt-1 text-xs text-rose-400/90 font-mono">
                  {error}
                </p>
              </div>
            </div>
          )}

          {/* Project Path */}
          <div className="space-y-2">
            <label className="text-xs font-mono uppercase tracking-widest text-slate-500">
              GitLab Project Path
            </label>

            <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 transition-all focus-within:border-cyan-500/60 focus-within:ring-2 focus-within:ring-cyan-500/10">
              <FolderGit2 className="h-4 w-4 text-slate-500" />

              <input
                type="text"
                placeholder="e.g. username/repo-name"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                disabled={submitting}
                className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none font-mono"
              />
            </div>
          </div>

          {/* Grid */}
          <div className="grid grid-cols-2 gap-4">

            {/* Pipeline ID */}
            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-widest text-slate-500">
                Pipeline ID
              </label>

              <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 transition-all focus-within:border-cyan-500/60 focus-within:ring-2 focus-within:ring-cyan-500/10">
                <Hash className="h-4 w-4 text-slate-500" />

                <input
                  type="text"
                  placeholder="12345678"
                  value={pipelineId}
                  onChange={(e) => setPipelineId(e.target.value)}
                  disabled={submitting}
                  className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none font-mono"
                />
              </div>
            </div>

            {/* Branch */}
            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-widest text-slate-500">
                Branch / Commit Ref
              </label>

              <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 transition-all focus-within:border-cyan-500/60 focus-within:ring-2 focus-within:ring-cyan-500/10">
                <GitBranch className="h-4 w-4 text-slate-500" />

                <input
                  type="text"
                  value={commitSha}
                  onChange={(e) => setCommitSha(e.target.value)}
                  disabled={submitting}
                  className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none font-mono"
                />
              </div>
            </div>

          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="group relative inline-flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-all hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500 shadow-lg shadow-cyan-500/10"
          >

            {/* Animated shine */}
            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full" />

            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Initializing Gemini Agent Environment...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Initiate Autonomous Healing Workflow
              </>
            )}
          </button>

        </div>
      </form>
    </div>
  );
}