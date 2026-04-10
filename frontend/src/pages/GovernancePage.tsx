import { GovernanceKPIs } from '../components/governance/GovernanceKPIs';
import { ActiveMarketExposure } from '../components/governance/ActiveMarketExposure';
import { GuardianRiskValidation } from '../components/governance/GuardianRiskValidation';
import { GovernanceDecisionStream } from '../components/governance/GovernanceDecisionStream';
import { GovernanceSettingsPanel } from '../components/governance/GovernanceSettingsPanel';
import { useGovernancePositions } from '../hooks/useGovernancePositions';
import { useGovernanceStream } from '../hooks/useGovernanceStream';
import { useGovernanceSettings } from '../hooks/useGovernanceSettings';
import { usePortfolioStream } from '../hooks/usePortfolioStream';
import { SectionSkeleton } from '../components/LoadingIndicators';

export function GovernancePage() {
  const { positions, loading: posLoading, refresh: refreshPositions } = useGovernancePositions();
  const { items: streamItems, loading: streamLoading, refresh: refreshStream } = useGovernanceStream();
  const { settings, saving, update: updateSettings } = useGovernanceSettings();
  const { state: portfolioState, limits: portfolioLimits } = usePortfolioStream();

  const autoGuardian = settings?.enabled ?? false;

  function handleRefresh() {
    refreshPositions();
    refreshStream();
  }

  return (
    <div className="flex flex-col gap-4 p-4 h-full overflow-y-auto">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold tracking-widest text-text">GOVERNANCE</h1>
          <p className="text-[10px] text-text-dim mt-0.5">Position monitoring and risk enforcement</p>
        </div>
      </div>

      {/* KPI row */}
      {posLoading ? (
        <SectionSkeleton />
      ) : (
        <GovernanceKPIs positions={positions} portfolioState={portfolioState} />
      )}

      {/* Positions table */}
      {posLoading ? (
        <SectionSkeleton />
      ) : (
        <ActiveMarketExposure
          positions={positions}
          autoGuardian={autoGuardian}
          onAutoGuardianToggle={(v) => updateSettings({ enabled: v })}
          onRefresh={handleRefresh}
        />
      )}

      {/* Bottom row: left panel + stream */}
      <div className="flex gap-4 min-h-0">
        {/* Left: risk validation + settings */}
        <div className="flex flex-col gap-4 w-72 shrink-0">
          <GuardianRiskValidation portfolioState={portfolioState} limits={portfolioLimits} />
          {settings && (
            <GovernanceSettingsPanel
              settings={settings}
              saving={saving}
              onUpdate={updateSettings}
            />
          )}
        </div>

        {/* Right: decision stream */}
        <div className="flex-1 min-h-[400px]">
          {streamLoading ? (
            <SectionSkeleton />
          ) : (
            <GovernanceDecisionStream
              items={streamItems}
              executionMode={settings?.execution_mode ?? 'confirmation'}
              onRefresh={refreshStream}
            />
          )}
        </div>
      </div>
    </div>
  );
}
