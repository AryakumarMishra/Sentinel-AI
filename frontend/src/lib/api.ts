const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface RecoveryStep {
  timestamp: string;
  step: string;
  status: string;
  details: string;
}

export interface ProposedFix {
  file_path: string;
  explanation: string;
  content: string;
}

export interface RecoveryRecord {
  recovery_id: string;
  pipeline_id: number;
  project_name: string;
  commit_sha: string;
  start_time: string;
  status: string;
  steps: RecoveryStep[];
  proposed_fix?: ProposedFix;
  approved_by_human: boolean;
}

export const api = {
  // Fetch all pipeline recoveries for the dashboard index grid
  async getRecoveries(): Promise<RecoveryRecord[]> {
    const res = await fetch(`${BASE_URL}/recoveries`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch recovery data records');
    return res.json();
  },

  // Fetch a specific recovery payload by its unique tracking UUID
  async getRecoveryDetail(id: string): Promise<RecoveryRecord> {
    const res = await fetch(`${BASE_URL}/recoveries/${id}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch detailed tracker metrics');
    return res.json();
  },

  // Submit an engineer's approve/reject decision to our pipeline orchestrator
  async sendDecision(id: string, approve: boolean): Promise<{ status: string; message: string }> {
    const res = await fetch(`${BASE_URL}/recoveries/${id}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve }),
    });
    if (!res.ok) throw new Error('Failed to transmit operator authorization matrix');
    return res.json();
  },

  // Manually queue up a healing run on a target repository
  async triggerManualHealing(project_path: string, pipeline_id: number, commit_sha: string): Promise<{ status: string; recovery_id: string }> {
    const res = await fetch(`${BASE_URL}/recoveries/manual-trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path, pipeline_id, commit_sha }),
    });
    if (!res.ok) throw new Error('Failed to submit manual workflow execution ticket');
    return res.json();
  }
};
