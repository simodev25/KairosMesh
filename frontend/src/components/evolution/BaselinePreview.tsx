interface BaselinePreviewProps {
  systemPrompt: string;
  userPromptTemplate: string;
  skills: string[];
}

export function BaselinePreview({ systemPrompt, userPromptTemplate, skills }: BaselinePreviewProps) {
  return (
    <section className="hw-surface p-4 space-y-3">
      <div className="section-header">
        <span className="section-title">BASELINE PREVIEW</span>
      </div>

      <div>
        <div className="micro-label">System prompt</div>
        <pre className="max-h-32">{systemPrompt || 'Aucune baseline chargée.'}</pre>
      </div>

      <div>
        <div className="micro-label">User prompt template</div>
        <pre className="max-h-32">{userPromptTemplate || 'Aucune baseline chargée.'}</pre>
      </div>

      <div>
        <div className="micro-label">Skills</div>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {skills.length === 0 ? (
            <span className="text-[10px] text-text-dim">Aucune skill baseline</span>
          ) : (
            skills.map((skill) => (
              <span key={skill} className="text-[9px] px-2 py-1 rounded border border-border bg-surface-alt text-text-muted">
                {skill}
              </span>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
