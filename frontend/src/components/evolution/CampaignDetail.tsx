import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { EvolutionCandidate, EvolutionFitnessSeries, EvolutionPromotion } from '../../types/evolution';
import { PromptDiffViewer } from './PromptDiffViewer';
import { PromoteButton } from './PromoteButton';

interface CampaignDetailProps {
  candidates: EvolutionCandidate[];
  fitnessSeries: EvolutionFitnessSeries | null;
  loading: boolean;
  baselinePrompt: string;
  onPromote: (candidateId: number, options: { promote_prompt: boolean; promote_skills: boolean }) => Promise<void>;
  lastPromotion: EvolutionPromotion | null;
}

export function CampaignDetail({
  candidates,
  fitnessSeries,
  loading,
  baselinePrompt,
  onPromote,
  lastPromotion,
}: CampaignDetailProps) {
  const bestCandidate = [...candidates]
    .filter((candidate) => candidate.fitness_score != null)
    .sort((left, right) => Number(right.fitness_score || 0) - Number(left.fitness_score || 0))[0];

  return (
    <section className="hw-surface p-4 space-y-4">
      <div className="section-header">
        <span className="section-title">DÉTAIL CAMPAGNE</span>
      </div>

      {loading && <div className="text-[10px] text-text-dim">Chargement des détails...</div>}

      {!loading && (
        <>
          <div className="h-64 hw-surface-alt p-2">
            <div className="micro-label mb-2">Fitness series</div>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={fitnessSeries?.points ?? []}>
                <XAxis dataKey="generation" stroke="#5A5E6E" tick={{ fill: '#5A5E6E', fontSize: 10 }} />
                <YAxis stroke="#5A5E6E" tick={{ fill: '#5A5E6E', fontSize: 10 }} domain={[0, 1]} />
                <Tooltip contentStyle={{ backgroundColor: '#0a0a0f', border: '1px solid #00d4ff' }} />
                <Line type="monotone" dataKey="best" stroke="#00d4ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="avg" stroke="#4B7BF5" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="hw-surface-alt p-3">
              <div className="micro-label mb-2">Leaderboard</div>
              {candidates.length === 0 ? (
                <div className="text-[10px] text-text-dim">Aucun candidat évalué.</div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-auto">
                  {candidates
                    .slice()
                    .sort((left, right) => Number(right.fitness_score || 0) - Number(left.fitness_score || 0))
                    .map((candidate) => (
                      <div key={candidate.id} className="border border-border rounded px-2 py-1 text-[10px]">
                        <div className="flex justify-between">
                          <span>#{candidate.id} · gen {candidate.generation}</span>
                          <span className="text-cyan-300">{Number(candidate.fitness_score || 0).toFixed(3)}</span>
                        </div>
                        <div className="text-text-dim">{candidate.status}</div>
                      </div>
                    ))}
                </div>
              )}
            </div>

            <div className="hw-surface-alt p-3">
              <div className="micro-label mb-2">Generation log</div>
              <div className="space-y-1 max-h-64 overflow-auto text-[10px]">
                {candidates.map((candidate) => (
                  <div key={candidate.id} className="text-text-dim">
                    gen {candidate.generation} · candidate #{candidate.id} · {candidate.status} · fitness{' '}
                    {candidate.fitness_score != null ? candidate.fitness_score.toFixed(3) : '--'}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <PromptDiffViewer
            baselinePrompt={baselinePrompt}
            candidatePrompt={bestCandidate?.system_prompt ?? ''}
          />

          <div className="flex items-center justify-between">
            <PromoteButton
              disabled={!bestCandidate}
              onConfirm={async (options) => {
                if (!bestCandidate) return;
                await onPromote(bestCandidate.id, options);
              }}
            />
            {lastPromotion ? (
              <span className="text-[10px] text-green-400">Promotion #{lastPromotion.promotion_id} créée</span>
            ) : (
              <span className="text-[10px] text-text-dim">Aucune promotion effectuée</span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
