import { FormEvent, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { ConnectorConfig, LlmSummary, MetaApiAccount, PromptTemplate } from '../types';

const PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'EURGBP'];
const TIMEFRAMES = ['M5', 'M15', 'H1', 'H4', 'D1'];

export function ConnectorsPage() {
  const { token } = useAuth();
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [accounts, setAccounts] = useState<MetaApiAccount[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [summary, setSummary] = useState<LlmSummary | null>(null);
  const [memoryResults, setMemoryResults] = useState<Array<Record<string, unknown>>>([]);

  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [accountLabel, setAccountLabel] = useState('Paper Account');
  const [accountId, setAccountId] = useState('');
  const [accountRegion, setAccountRegion] = useState('new-york');

  const [promptAgent, setPromptAgent] = useState('bullish-researcher');
  const [promptSystem, setPromptSystem] = useState('You are a bullish forex researcher.');
  const [promptUser, setPromptUser] = useState('Pair: {pair}\nSignals: {signals_json}\nMemory: {memory_context}');

  const [memoryPair, setMemoryPair] = useState('EURUSD');
  const [memoryTimeframe, setMemoryTimeframe] = useState('H1');
  const [memoryQuery, setMemoryQuery] = useState('recent bullish context');

  const loadAll = async () => {
    if (!token) return;
    try {
      const [c, a, p, s] = await Promise.all([
        api.listConnectors(token),
        api.listMetaApiAccounts(token),
        api.listPrompts(token),
        api.llmSummary(token),
      ]);
      setConnectors(c as ConnectorConfig[]);
      setAccounts(a as MetaApiAccount[]);
      setPrompts(p as PromptTemplate[]);
      setSummary(s as LlmSummary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cannot load admin data');
    }
  };

  useEffect(() => {
    void loadAll();
  }, [token]);

  const toggleConnector = async (connector: ConnectorConfig) => {
    if (!token) return;
    await api.updateConnector(token, connector.connector_name, {
      enabled: !connector.enabled,
      settings: connector.settings,
    });
    await loadAll();
  };

  const testConnector = async (name: string) => {
    if (!token) return;
    try {
      const result = (await api.testConnector(token, name)) as Record<string, unknown>;
      setTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connector test failed');
    }
  };

  const createAccount = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    try {
      await api.createMetaApiAccount(token, {
        label: accountLabel,
        account_id: accountId,
        region: accountRegion,
        enabled: true,
        is_default: accounts.length === 0,
      });
      setAccountLabel('Paper Account');
      setAccountId('');
      setAccountRegion('new-york');
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cannot create account');
    }
  };

  const setDefaultAccount = async (account: MetaApiAccount) => {
    if (!token) return;
    await api.updateMetaApiAccount(token, account.id, { is_default: true });
    await loadAll();
  };

  const createPrompt = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    try {
      await api.createPrompt(token, {
        agent_name: promptAgent,
        system_prompt: promptSystem,
        user_prompt_template: promptUser,
      });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cannot create prompt');
    }
  };

  const activatePrompt = async (prompt: PromptTemplate) => {
    if (!token) return;
    await api.activatePrompt(token, prompt.id);
    await loadAll();
  };

  const searchMemory = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    try {
      const result = (await api.searchMemory(token, {
        pair: memoryPair,
        timeframe: memoryTimeframe,
        query: memoryQuery,
        limit: 10,
      })) as { results: Array<Record<string, unknown>> };
      setMemoryResults(result.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Memory search failed');
    }
  };

  return (
    <div className="dashboard-grid">
      <section className="card">
        <h2>Administration connecteurs</h2>
        {error && <p className="alert">{error}</p>}
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Actif</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {connectors.map((connector) => (
              <tr key={connector.id}>
                <td>{connector.connector_name}</td>
                <td>
                  <span className={`badge ${connector.enabled ? 'ok' : 'blocked'}`}>{connector.enabled ? 'enabled' : 'disabled'}</span>
                </td>
                <td>
                  <button onClick={() => void toggleConnector(connector)}>{connector.enabled ? 'Disable' : 'Enable'}</button>
                  <button onClick={() => void testConnector(connector.connector_name)}>Test</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card stats">
        <h3>LLM Telemetry</h3>
        <div className="stats-grid">
          <div>
            <span>Calls</span>
            <strong>{summary?.total_calls ?? 0}</strong>
          </div>
          <div>
            <span>Success</span>
            <strong>{summary?.successful_calls ?? 0}</strong>
          </div>
          <div>
            <span>Latency ms</span>
            <strong>{summary?.average_latency_ms ?? 0}</strong>
          </div>
          <div>
            <span>Cost USD</span>
            <strong>{summary?.total_cost_usd ?? 0}</strong>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Comptes MetaApi</h3>
        <form className="form-grid inline" onSubmit={createAccount}>
          <label>
            Label
            <input value={accountLabel} onChange={(e) => setAccountLabel(e.target.value)} required />
          </label>
          <label>
            Account ID
            <input value={accountId} onChange={(e) => setAccountId(e.target.value)} required />
          </label>
          <label>
            Region
            <input value={accountRegion} onChange={(e) => setAccountRegion(e.target.value)} required />
          </label>
          <button>Ajouter compte</button>
        </form>
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th>Account ID</th>
              <th>Region</th>
              <th>Status</th>
              <th>Default</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <tr key={account.id}>
                <td>{account.label}</td>
                <td>{account.account_id}</td>
                <td>{account.region}</td>
                <td><span className={`badge ${account.enabled ? 'ok' : 'blocked'}`}>{account.enabled ? 'enabled' : 'disabled'}</span></td>
                <td>
                  {account.is_default ? (
                    <span className="badge ok">default</span>
                  ) : (
                    <button onClick={() => void setDefaultAccount(account)}>Set default</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Prompts versionnés</h3>
        <form className="form-grid" onSubmit={createPrompt}>
          <label>
            Agent
            <input value={promptAgent} onChange={(e) => setPromptAgent(e.target.value)} />
          </label>
          <label>
            System prompt
            <textarea value={promptSystem} onChange={(e) => setPromptSystem(e.target.value)} rows={3} />
          </label>
          <label>
            User template
            <textarea value={promptUser} onChange={(e) => setPromptUser(e.target.value)} rows={4} />
          </label>
          <button>Créer version</button>
        </form>
        <table>
          <thead>
            <tr>
              <th>Agent</th>
              <th>Version</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {prompts.map((prompt) => (
              <tr key={prompt.id}>
                <td>{prompt.agent_name}</td>
                <td>v{prompt.version}</td>
                <td><span className={`badge ${prompt.is_active ? 'ok' : 'blocked'}`}>{prompt.is_active ? 'active' : 'inactive'}</span></td>
                <td>
                  {!prompt.is_active && <button onClick={() => void activatePrompt(prompt)}>Activer</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Mémoire long-terme</h3>
        <form className="form-grid inline" onSubmit={searchMemory}>
          <label>
            Pair
            <select value={memoryPair} onChange={(e) => setMemoryPair(e.target.value)}>
              {PAIRS.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select value={memoryTimeframe} onChange={(e) => setMemoryTimeframe(e.target.value)}>
              {TIMEFRAMES.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Query
            <input value={memoryQuery} onChange={(e) => setMemoryQuery(e.target.value)} />
          </label>
          <button>Search</button>
        </form>
        <pre>{JSON.stringify(memoryResults, null, 2)}</pre>
      </section>

      <section className="card">
        <h3>Résultat test connecteur</h3>
        <pre>{JSON.stringify(testResult, null, 2)}</pre>
      </section>
    </div>
  );
}
