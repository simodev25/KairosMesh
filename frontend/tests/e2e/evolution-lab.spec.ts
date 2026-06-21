import { expect, test, type Page } from '@playwright/test';

/* ─────────────────── Helpers ─────────────────── */

function asJson(body: unknown, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

/* ─────────────────── Mock Data ─────────────────── */

const MOCK_CAMPAIGNS = [
  {
    id: 1,
    name: 'Evolution technical-analyst gpt-4o',
    agent_name: 'technical-analyst',
    provider: 'openai',
    model_name: 'gpt-4o',
    model_parameters: {},
    status: 'running',
    max_iterations: 100,
    max_candidates: 50,
    max_llm_calls: 5000,
    budget_usd_limit: 10.0,
    evaluation_config: {},
    best_candidate_id: 3,
    celery_task_id: 'task-abc-123',
    created_by_id: 1,
    created_at: '2026-06-20T10:00:00Z',
    started_at: '2026-06-20T10:01:00Z',
    completed_at: null,
    error: null,
  },
  {
    id: 2,
    name: 'Evolution trader-agent gpt-4o',
    agent_name: 'trader-agent',
    provider: 'openai',
    model_name: 'gpt-4o',
    model_parameters: {},
    status: 'completed',
    max_iterations: 100,
    max_candidates: 50,
    max_llm_calls: 5000,
    budget_usd_limit: 10.0,
    evaluation_config: {},
    best_candidate_id: 12,
    celery_task_id: 'task-def-456',
    created_by_id: 1,
    created_at: '2026-06-18T08:00:00Z',
    started_at: '2026-06-18T08:01:00Z',
    completed_at: '2026-06-18T12:00:00Z',
    error: null,
  },
];

const MOCK_CANDIDATES = [
  {
    id: 3,
    campaign_id: 1,
    generation: 15,
    parent_candidate_id: 2,
    system_prompt: 'You are a technical analyst specializing in forex markets. ALWAYS prioritize trend confirmation from 2+ timeframes before issuing a signal.',
    user_prompt_template: 'Analyze {pair} on {timeframe} with confidence scoring (0-1).',
    skills: ['Analyze exclusively the technical facts', 'Strictly respect the runtime directional convention'],
    fitness_score: 0.847,
    metrics_summary: { schema_validity: 0.95, completeness: 0.88, stability: 0.82 },
    llm_cost_usd: 0.45,
    llm_calls_count: 12,
    is_baseline: false,
    status: 'evaluated',
    created_at: '2026-06-20T14:30:00Z',
  },
  {
    id: 1,
    campaign_id: 1,
    generation: 0,
    parent_candidate_id: null,
    system_prompt: 'You are a technical analyst specializing in forex markets.',
    user_prompt_template: 'Analyze {pair} on {timeframe}.',
    skills: ['Analyze exclusively the technical facts'],
    fitness_score: 0.688,
    metrics_summary: { schema_validity: 0.90, completeness: 0.70, stability: 0.65 },
    llm_cost_usd: 0.0,
    llm_calls_count: 0,
    is_baseline: true,
    status: 'evaluated',
    created_at: '2026-06-20T10:01:00Z',
  },
];

const MOCK_FITNESS_SERIES = {
  points: [
    { generation: 0, best: 0.688, avg: 0.688 },
    { generation: 5, best: 0.742, avg: 0.71 },
    { generation: 10, best: 0.801, avg: 0.76 },
    { generation: 15, best: 0.847, avg: 0.79 },
  ],
};

const MOCK_PROMPTS = [
  {
    id: 1,
    agent_name: 'technical-analyst',
    version: 1,
    is_active: true,
    system_prompt: 'You are a technical analyst specializing in forex markets.',
    user_prompt_template: 'Analyze {pair} on {timeframe}.',
    notes: 'seed default',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const MOCK_SKILLS = [
  {
    id: 1,
    agent_name: 'technical-analyst',
    version: 1,
    is_active: true,
    skills: ['Analyze exclusively the technical facts', 'Strictly respect the runtime directional convention'],
    notes: 'seed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

/* ─────────────────── Mock Setup ─────────────────── */

async function mockEvolutionApi(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token');
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname;

    // Auth
    if (path.endsWith('/auth/me')) {
      return route.fulfill(asJson({ id: 1, email: 'admin@local.dev', role: 'admin', is_active: true }));
    }

    // Campaigns list
    if (path.endsWith('/evolution/campaigns') && method === 'GET') {
      return route.fulfill(asJson({ items: MOCK_CAMPAIGNS, total: 2 }));
    }

    // Campaign detail
    if (path.match(/\/evolution\/campaigns\/\d+$/) && method === 'GET') {
      const id = parseInt(path.split('/').pop()!);
      const campaign = MOCK_CAMPAIGNS.find((c) => c.id === id);
      return route.fulfill(asJson(campaign ?? { detail: 'Not found' }, campaign ? 200 : 404));
    }

    // Candidates
    if (path.match(/\/evolution\/campaigns\/\d+\/candidates/) && method === 'GET') {
      return route.fulfill(asJson({ items: MOCK_CANDIDATES, total: 2 }));
    }

    // Fitness series
    if (path.match(/\/evolution\/campaigns\/\d+\/fitness-series/) && method === 'GET') {
      return route.fulfill(asJson(MOCK_FITNESS_SERIES));
    }

    // Create campaign
    if (path.endsWith('/evolution/campaigns') && method === 'POST') {
      return route.fulfill(asJson({ ...MOCK_CAMPAIGNS[0], id: 99, status: 'pending' }, 201));
    }

    // Cancel campaign
    if (path.match(/\/evolution\/campaigns\/\d+\/cancel/) && method === 'POST') {
      return route.fulfill(asJson({ ...MOCK_CAMPAIGNS[0], status: 'cancelled' }));
    }

    // Promote candidate
    if (path.match(/\/evolution\/candidates\/\d+\/promote/) && method === 'POST') {
      return route.fulfill(asJson({
        id: 1,
        campaign_id: 1,
        candidate_id: 3,
        prompt_template_id: 5,
        agent_skill_id: 3,
        promoted_by_id: 1,
        created_at: '2026-06-21T15:00:00Z',
      }, 201));
    }

    // Prompts
    if (path.endsWith('/prompts') && method === 'GET') {
      return route.fulfill(asJson(MOCK_PROMPTS));
    }

    // Agent skills
    if (path.match(/\/agents\/[\w-]+\/skills/) && method === 'GET') {
      return route.fulfill(asJson(MOCK_SKILLS));
    }

    // Connectors (needed for some auth flows)
    if (path.endsWith('/connectors') && method === 'GET') {
      return route.fulfill(asJson([
        { id: 1, connector_name: 'ollama', enabled: true, settings: { provider: 'ollama', default_model: 'gpt-4o', agent_models: {}, agent_llm_enabled: {} } },
      ]));
    }

    // Fallback
    return route.fulfill(asJson({ detail: 'Not mocked' }, 404));
  });
}

/* ─────────────────── Tests ─────────────────── */

test.describe('Evolution Lab - Navigation et affichage', () => {
  test('la page est accessible et affiche le titre', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.locator('text=EVOLUTION LAB')).toBeVisible();
  });

  test('les 3 tabs sont présents', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.getByRole('tab', { name: 'CAMPAGNES' })).toBeVisible();
    await expect(page.getByRole('tab', { name: '+ NOUVELLE' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'LEADERBOARD' })).toBeVisible();
  });

  test('le tab Campagnes est sélectionné par défaut', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.getByRole('tab', { name: 'CAMPAGNES' })).toHaveAttribute('aria-selected', 'true');
  });
});

test.describe('Evolution Lab - Liste des campagnes', () => {
  test('affiche les campagnes actives et terminées', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.locator('text=technical-analyst')).toBeVisible();
    await expect(page.locator('text=trader-agent')).toBeVisible();
  });

  test('affiche le statut running pour la campagne active', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.locator('text=running').first()).toBeVisible();
  });

  test('affiche le statut completed pour la campagne terminée', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.locator('text=completed').first()).toBeVisible();
  });
});

test.describe('Evolution Lab - Formulaire nouvelle campagne', () => {
  test('le formulaire affiche les agents sélectionnables', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await page.getByRole('tab', { name: '+ NOUVELLE' }).click();
    await expect(page.getByRole('tabpanel')).toBeVisible();
    // Vérifie qu'au moins quelques agents sont listés
    await expect(page.locator('text=technical-analyst')).toBeVisible();
    await expect(page.locator('text=trader-agent')).toBeVisible();
    await expect(page.locator('text=risk-manager')).toBeVisible();
  });

  test('les champs iterations et candidates ont les valeurs par défaut', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await page.getByRole('tab', { name: '+ NOUVELLE' }).click();
    // Chercher les inputs avec valeurs par défaut 100 et 50
    const iterInput = page.locator('input[value="100"]');
    const candInput = page.locator('input[value="50"]');
    await expect(iterInput.first()).toBeVisible();
    await expect(candInput.first()).toBeVisible();
  });

  test('le bouton de lancement est présent', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await page.getByRole('tab', { name: '+ NOUVELLE' }).click();
    await expect(page.getByRole('button', { name: /lancer|créer|démarrer/i })).toBeVisible();
  });
});

test.describe('Evolution Lab - Détail campagne', () => {
  test('affiche le leaderboard des candidats', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    // La première campagne devrait être sélectionnée par défaut et afficher les candidats
    await expect(page.locator('text=0.847').first()).toBeVisible({ timeout: 5000 });
  });

  test('affiche le score baseline', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await expect(page.locator('text=0.688').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Evolution Lab - Leaderboard global', () => {
  test('le tab leaderboard affiche les top candidats', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    await page.getByRole('tab', { name: 'LEADERBOARD' }).click();
    await expect(page.locator('text=TOP CANDIDATS')).toBeVisible();
    await expect(page.locator('text=0.847')).toBeVisible();
  });
});

test.describe('Evolution Lab - Promotion', () => {
  test('un bouton promouvoir est disponible', async ({ page }) => {
    await mockEvolutionApi(page);
    await page.goto('/evolution-lab');
    // Attendre le chargement des candidats
    await expect(page.locator('text=0.847').first()).toBeVisible({ timeout: 5000 });
    // Chercher un bouton de promotion
    const promoteBtn = page.getByRole('button', { name: /promouvoir|promote/i }).first();
    await expect(promoteBtn).toBeVisible();
  });
});
