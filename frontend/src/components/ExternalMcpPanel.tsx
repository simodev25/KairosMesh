import { useState } from 'react';
import type { ExternalMcpConfig } from '../types';

interface Props {
  agentName: string;
  mcps: ExternalMcpConfig[];
  agentTools: Record<string, boolean>;  // tool_id -> enabled
  onToggleTool: (toolId: string, enabled: boolean) => void;
  onAddMcp: () => void;
  onDeleteMcp: (mcpId: string) => void;
  onRefreshMcp: (mcp: ExternalMcpConfig) => void;
}

export function ExternalMcpPanel({
  agentName,
  mcps,
  agentTools,
  onToggleTool,
  onAddMcp,
  onDeleteMcp,
  onRefreshMcp,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const agentMcps = mcps.filter((m) => m.assigned_agents.includes(agentName));

  return (
    <div style={{ marginTop: '1rem', borderTop: '1px solid #334155', paddingTop: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          External MCPs
        </span>
        <button
          onClick={onAddMcp}
          style={{
            fontSize: '0.75rem',
            padding: '2px 10px',
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '4px',
            color: '#60a5fa',
            cursor: 'pointer',
          }}
        >
          + Add MCP
        </button>
      </div>

      {agentMcps.length === 0 && (
        <p style={{ fontSize: '0.75rem', color: '#475569', fontStyle: 'italic' }}>No external MCPs connected.</p>
      )}

      {agentMcps.map((mcp) => {
        const isExpanded = expandedId === mcp.id;
        const statusColor = mcp.discovery_status === 'ok' ? '#22c55e' : mcp.discovery_status === 'error' ? '#ef4444' : '#94a3b8';

        return (
          <div key={mcp.id} style={{ marginBottom: '0.5rem', background: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', cursor: 'pointer' }}
              onClick={() => setExpandedId(isExpanded ? null : mcp.id)}
            >
              <span style={{ fontSize: '0.7rem', color: statusColor }}>●</span>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e8f0', flex: 1 }}>{mcp.name}</span>
              <span style={{ fontSize: '0.65rem', color: '#475569', flex: 2 }}>{mcp.url}</span>
              <button
                onClick={(e) => { e.stopPropagation(); onRefreshMcp(mcp); }}
                title="Re-discover tools"
                style={{ fontSize: '0.65rem', padding: '1px 6px', background: 'none', border: '1px solid #334155', borderRadius: '3px', color: '#60a5fa', cursor: 'pointer' }}
              >
                ↺
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteMcp(mcp.id); }}
                title="Remove from agent"
                style={{ fontSize: '0.65rem', padding: '1px 6px', background: 'none', border: '1px solid #334155', borderRadius: '3px', color: '#f87171', cursor: 'pointer' }}
              >
                ✕
              </button>
              <span style={{ color: '#475569', fontSize: '0.7rem' }}>{isExpanded ? '▲' : '▼'}</span>
            </div>

            {isExpanded && (
              <div style={{ padding: '0.25rem 0.75rem 0.75rem' }}>
                {mcp.discovered_tools.length === 0 && (
                  <p style={{ fontSize: '0.7rem', color: '#475569', fontStyle: 'italic' }}>No tools discovered.</p>
                )}
                {mcp.discovered_tools.map((tool) => {
                  const enabled = agentTools[tool.tool_id] ?? false;
                  return (
                    <div key={tool.tool_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '3px 0' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', flex: 1 }}>
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => onToggleTool(tool.tool_id, e.target.checked)}
                        />
                        <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>{tool.label || tool.tool_id}</span>
                      </label>
                      <span style={{ fontSize: '0.65rem', color: '#475569', flex: 2 }}>{tool.description}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
