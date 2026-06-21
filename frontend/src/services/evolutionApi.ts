import { api } from '../api/client';
import type {
  EvolutionCampaign,
  EvolutionCampaignCreatePayload,
  EvolutionCampaignList,
  EvolutionCandidate,
  EvolutionFitnessSeries,
  EvolutionPromotion,
} from '../types/evolution';

export const evolutionApi = {
  createCampaign: (token: string, payload: EvolutionCampaignCreatePayload) =>
    api.createEvolutionCampaign(token, payload) as Promise<EvolutionCampaign>,

  listCampaigns: (token: string, params: { status?: string; agent_name?: string; offset?: number; limit?: number } = {}) =>
    api.listEvolutionCampaigns(token, params) as Promise<EvolutionCampaignList>,

  getCampaign: (token: string, campaignId: number) =>
    api.getEvolutionCampaign(token, campaignId) as Promise<EvolutionCampaign>,

  cancelCampaign: (token: string, campaignId: number) =>
    api.cancelEvolutionCampaign(token, campaignId) as Promise<{ id: number; status: string }>,

  listCandidates: (token: string, campaignId: number, sort: 'generation' | 'fitness' = 'generation') =>
    api.listEvolutionCandidates(token, campaignId, sort) as Promise<{ items: EvolutionCandidate[] }>,

  getFitnessSeries: (token: string, campaignId: number) =>
    api.getEvolutionFitnessSeries(token, campaignId) as Promise<EvolutionFitnessSeries>,

  promoteCandidate: (
    token: string,
    candidateId: number,
    payload: { promote_prompt: boolean; promote_skills: boolean },
  ) => api.promoteEvolutionCandidate(token, candidateId, payload) as Promise<EvolutionPromotion>,
};
