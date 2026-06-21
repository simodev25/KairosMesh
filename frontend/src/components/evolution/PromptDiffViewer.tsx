interface PromptDiffViewerProps {
  baselinePrompt: string;
  candidatePrompt: string;
}

export function PromptDiffViewer({ baselinePrompt, candidatePrompt }: PromptDiffViewerProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <section className="hw-surface-alt p-3">
        <div className="micro-label">Baseline</div>
        <pre className="max-h-64">{baselinePrompt || 'N/A'}</pre>
      </section>
      <section className="hw-surface-alt p-3 border-cyan-500/30">
        <div className="micro-label">Candidat</div>
        <pre className="max-h-64">{candidatePrompt || 'N/A'}</pre>
      </section>
    </div>
  );
}
