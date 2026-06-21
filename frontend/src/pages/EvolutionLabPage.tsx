import { useEffect, useMemo, useState } from 'react';
import { CampaignForm } from '../components/evolution/CampaignForm';
import { CampaignCard } from '../components/evolution/CampaignCard';
import { CampaignDetail } from '../components/evolution/CampaignDetail';
import { BaselinePreview } from '../components/evolution/BaselinePreview';
import { evolutionApi } from '../services/evolutionApi';
import { useAuth } from '../hooks/useAuth';
import type {
  EvolutionCampaign,
  EvolutionCampaignCreatePayload,
  EvolutionCandidate,
  EvolutionFitnessSeries,
  EvolutionPromotion,
} from '../types/evolution';

type TabId = 'campaigns' | 'new' | 'leaderboard';

const TAB_LABELS: Record<TabId, string> = {
  campaigns: 'CAMPAGNES',
  new: '+ NOUVELLE',
  leaderboard: 'LEADERBOARD',
};

export default function EvolutionLabPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<TabId>('campaigns');
  const [campaigns, setCampaigns] = useState<EvolutionCampaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [candidates, setCandidates] = useState<EvolutionCandidate[]>([]);
  const [fitnessSeries, setFitnessSeries] = useState<EvolutionFitnessSeries | null>(null);
  const [lastPromotion, setLastPromotion] = useState<EvolutionPromotion | null>(null);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCampaign = useMemo(
    () => campaigns.find((campaign) => campaign.id === selectedCampaignId) ?? null,
    [campaigns, selectedCampaignId],
  );

  const loadCampaigns = async () => {
    if (!token) return;
    setLoadingCampaigns(true);
    setError(null);
    try {
      const response = await evolutionApi.listCampaigns(token, { limit: 100 });
      setCampaigns(response.items);
      if (!selectedCampaignId && response.items.length > 0) {
        setSelectedCampaignId(response.items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de charger les campagnes.');
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const loadCampaignDetail = async (campaignId: number) => {
    if (!token) return;
    setLoadingDetail(true);
    setError(null);
    try {
      const [candidateResponse, seriesResponse] = await Promise.all([
        evolutionApi.listCandidates(token, campaignId, 'fitness'),
        evolutionApi.getFitnessSeries(token, campaignId),
      ]);
      setCandidates(candidateResponse.items);
      setFitnessSeries(seriesResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de charger les détails de campagne.');
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    void loadCampaigns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (selectedCampaignId != null) {
      void loadCampaignDetail(selectedCampaignId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCampaignId]);

  const handleCreateCampaign = async (payload: EvolutionCampaignCreatePayload) => {
    if (!token) return;
    setCreating(true);
    setError(null);
    try {
      const created = await evolutionApi.createCampaign(token, payload);
      setTab('campaigns');
      await loadCampaigns();
      setSelectedCampaignId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Création de campagne impossible.');
    } finally {
      setCreating(false);
    }
  };

  const handlePromote = async (
    candidateId: number,
    options: { promote_prompt: boolean; promote_skills: boolean },
  ) => {
    if (!token || selectedCampaignId == null) return;
    try {
      const promotion = await evolutionApi.promoteCandidate(token, candidateId, options);
      setLastPromotion(promotion);
      await loadCampaignDetail(selectedCampaignId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Promotion impossible.');
    }
  };

  const baselineCandidate = candidates.find((candidate) => candidate.is_baseline);
  const topCandidates = useMemo(
    () =>
      [...candidates]
        .filter((candidate) => candidate.fitness_score != null)
        .sort((left, right) => Number(right.fitness_score || 0) - Number(left.fitness_score || 0))
        .slice(0, 10),
    [candidates],
  );

  return (
    <div className="space-y-4" style={{ background: '#0a0a0f', minHeight: 'calc(100vh - 96px)', padding: '8px' }}>
      <div className="section-header">
        <span className="section-title" style={{ color: '#00d4ff' }}>EVOLUTION LAB</span>
      </div>

      <div role="tablist" aria-label="Navigation Evolution Lab" className="flex flex-wrap gap-2">
        {(['campaigns', 'new', 'leaderboard'] as const).map((tabId) => (
          <button
            key={tabId}
            id={`tab-${tabId}`}
            role="tab"
            aria-selected={tab === tabId}
            aria-controls={`panel-${tabId}`}
            tabIndex={tab === tabId ? 0 : -1}
            onClick={() => setTab(tabId)}
            className={`px-3 py-2 rounded border text-[10px] tracking-[0.12em] ${
              tab === tabId ? 'border-cyan-400 text-cyan-300 bg-cyan-500/10' : 'border-border text-text-muted'
            }`}
          >
            {TAB_LABELS[tabId]}
          </button>
        ))}
      </div>

      {error && <div className="alert">{error}</div>}

      {tab === 'campaigns' && (
        <div id="panel-campaigns" role="tabpanel" aria-labelledby="tab-campaigns" className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <section className="space-y-3">
            {loadingCampaigns ? (
              <div className="hw-surface p-4 text-[10px] text-text-dim">Chargement des campagnes...</div>
            ) : campaigns.length === 0 ? (
              <div className="hw-surface p-4 text-[10px] text-text-dim">Aucune campagne disponible.</div>
            ) : (
              campaigns.map((campaign) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  selected={campaign.id === selectedCampaignId}
                  onSelect={setSelectedCampaignId}
                />
              ))
            )}
          </section>

          <section className="xl:col-span-2 space-y-4">
            {selectedCampaign ? (
              <>
                <CampaignDetail
                  candidates={candidates}
                  fitnessSeries={fitnessSeries}
                  loading={loadingDetail}
                  baselinePrompt={baselineCandidate?.system_prompt ?? ''}
                  onPromote={handlePromote}
                  lastPromotion={lastPromotion}
                />
                <BaselinePreview
                  systemPrompt={baselineCandidate?.system_prompt ?? ''}
                  userPromptTemplate={baselineCandidate?.user_prompt_template ?? ''}
                  skills={baselineCandidate?.skills ?? []}
                />
              </>
            ) : (
              <div className="hw-surface p-4 text-[10px] text-text-dim">Sélectionnez une campagne.</div>
            )}
          </section>
        </div>
      )}

      {tab === 'new' && (
        <div id="panel-new" role="tabpanel" aria-labelledby="tab-new">
          <CampaignForm onSubmit={handleCreateCampaign} loading={creating} />
        </div>
      )}

      {tab === 'leaderboard' && (
        <div id="panel-leaderboard" role="tabpanel" aria-labelledby="tab-leaderboard" className="hw-surface p-4">
          <div className="section-header">
            <span className="section-title">TOP CANDIDATS</span>
          </div>
          {topCandidates.length === 0 ? (
            <p className="text-[10px] text-text-dim">Aucun candidat évalué pour le moment.</p>
          ) : (
            <div className="space-y-2">
              {topCandidates.map((candidate, index) => (
                <div key={candidate.id} className="flex items-center justify-between border border-border rounded px-3 py-2 text-[10px]">
                  <span>#{index + 1} · candidate {candidate.id} · {candidate.status}</span>
                  <span className="text-cyan-300">{Number(candidate.fitness_score || 0).toFixed(3)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
