import { useState } from 'react';
import { api } from '../api/client';

interface DiscoveredTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

interface Props {
  agentName: string;
  token: string;
  onClose: () => void;
  onSaved: (mcpId: string) => void;
}

export function AddExternalMcpModal({ agentName, token, onClose, onSaved }: Props) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [headers, setHeaders] = useState<Array<{ key: string; value: string }>>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredTools, setDiscoveredTools] = useState<DiscoveredTool[] | null>(null);
  const [discoverError, setDiscoverError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const headersDict = Object.fromEntries(headers.filter((h) => h.key).map((h) => [h.key, h.value]));

  const handleDiscover = async () => {
    if (!url.trim()) return;
    setDiscovering(true);
    setDiscoverError(null);
    setDiscoveredTools(null);
    try {
      const result = await api.discoverExternalMcp(token, url.trim(), headersDict);
      setDiscoveredTools(result.tools);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : 'Failed to reach MCP server');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim() || !url.trim() || !discoveredTools) return;
    setSaving(true);
    try {
      const mcpNameSlug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const discovered = discoveredTools.map((t) => ({
        tool_id: `ext__${mcpNameSlug}__${t.name}`,
        label: t.name,
        description: t.description,
        input_schema: t.inputSchema,
        discovery_status: 'ok' as const,
      }));
      const result = await api.saveExternalMcp(token, {
        name: name.trim(),
        url: url.trim(),
        headers: headersDict,
        assigned_agents: [agentName],
        discovered_tools: discovered,
      });
      onSaved(result.id);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const addHeader = () => setHeaders((h) => [...h, { key: '', value: '' }]);
  const updateHeader = (i: number, field: 'key' | 'value', val: string) =>
    setHeaders((h) => h.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));
  const removeHeader = (i: number) => setHeaders((h) => h.filter((_, idx) => idx !== i));

  const overlay: React.CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };
  const modal: React.CSSProperties = {
    background: '#0f172a', border: '1px solid #334155', borderRadius: '8px',
    padding: '1.5rem', width: '480px', maxHeight: '80vh', overflowY: 'auto',
    display: 'flex', flexDirection: 'column', gap: '0.75rem',
  };
  const inputStyle: React.CSSProperties = {
    width: '100%', background: '#1e293b', border: '1px solid #334155',
    borderRadius: '4px', padding: '6px 10px', color: '#e2e8f0', fontSize: '0.85rem',
    boxSizing: 'border-box',
  };
  const labelStyle: React.CSSProperties = { fontSize: '0.75rem', color: '#94a3b8', marginBottom: '2px', display: 'block' };
  const btnPrimary: React.CSSProperties = {
    padding: '6px 16px', background: '#2563eb', border: 'none', borderRadius: '4px',
    color: '#fff', fontSize: '0.85rem', cursor: 'pointer',
  };
  const btnSecondary: React.CSSProperties = {
    padding: '6px 16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '4px',
    color: '#94a3b8', fontSize: '0.85rem', cursor: 'pointer',
  };

  return (
    <div style={overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modal}>
        <h3 style={{ margin: 0, color: '#e2e8f0', fontSize: '1rem' }}>Add External MCP Server</h3>
        <p style={{ margin: 0, fontSize: '0.75rem', color: '#64748b' }}>Agent: <strong>{agentName}</strong></p>

        <div>
          <label style={labelStyle}>Name</label>
          <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="My Finance MCP" />
        </div>

        <div>
          <label style={labelStyle}>URL</label>
          <input style={inputStyle} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8001" />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>Headers</label>
            <button onClick={addHeader} style={{ ...btnSecondary, padding: '2px 8px', fontSize: '0.7rem' }}>+ Add</button>
          </div>
          {headers.map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '4px' }}>
              <input
                style={{ ...inputStyle, flex: 1 }}
                placeholder="Key"
                value={h.key}
                onChange={(e) => updateHeader(i, 'key', e.target.value)}
              />
              <input
                style={{ ...inputStyle, flex: 2 }}
                placeholder="Value"
                value={h.value}
                onChange={(e) => updateHeader(i, 'value', e.target.value)}
              />
              <button onClick={() => removeHeader(i)} style={{ ...btnSecondary, padding: '2px 6px', color: '#f87171' }}>✕</button>
            </div>
          ))}
        </div>

        <button onClick={handleDiscover} disabled={!url.trim() || discovering} style={btnPrimary}>
          {discovering ? 'Discovering...' : 'Discover Tools'}
        </button>

        {discoverError && (
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#ef4444' }}>{discoverError}</p>
        )}

        {discoveredTools !== null && (
          <div>
            <p style={{ margin: '0 0 6px', fontSize: '0.75rem', color: '#94a3b8' }}>
              {discoveredTools.length} tool{discoveredTools.length !== 1 ? 's' : ''} discovered (all disabled by default):
            </p>
            {discoveredTools.map((t) => (
              <div key={t.name} style={{ fontSize: '0.75rem', color: '#cbd5e1', padding: '3px 0', borderBottom: '1px solid #1e293b' }}>
                <strong>{t.name}</strong> — {t.description}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
          <button onClick={onClose} style={btnSecondary}>Cancel</button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !discoveredTools || saving}
            style={{ ...btnPrimary, opacity: (!name.trim() || !discoveredTools || saving) ? 0.5 : 1 }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
