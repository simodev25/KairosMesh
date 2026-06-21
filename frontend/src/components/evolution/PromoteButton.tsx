import { useState } from 'react';

interface PromoteButtonProps {
  disabled?: boolean;
  loading?: boolean;
  onConfirm: (options: { promote_prompt: boolean; promote_skills: boolean }) => Promise<void>;
}

export function PromoteButton({ disabled = false, loading = false, onConfirm }: PromoteButtonProps) {
  const [open, setOpen] = useState(false);
  const [promotePrompt, setPromotePrompt] = useState(true);
  const [promoteSkills, setPromoteSkills] = useState(true);

  const close = () => setOpen(false);

  return (
    <>
      <button className="btn-primary" disabled={disabled || loading} onClick={() => setOpen(true)} type="button">
        {loading ? 'PROMOTION...' : 'PROMOUVOIR'}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center" role="dialog" aria-modal="true">
          <div className="hw-surface p-4 w-full max-w-md">
            <h3 className="section-title">CONFIRMER PROMOTION</h3>
            <p className="text-[10px] text-text-muted mt-2">
              Cette action crée de nouvelles versions (non actives) pour prompt et/ou skills.
            </p>

            <div className="space-y-2 mt-3 text-[10px]">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={promotePrompt} onChange={(e) => setPromotePrompt(e.target.checked)} />
                Promouvoir le prompt
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={promoteSkills} onChange={(e) => setPromoteSkills(e.target.checked)} />
                Promouvoir les skills
              </label>
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button type="button" className="btn-ghost" onClick={close}>ANNULER</button>
              <button
                type="button"
                className="btn-primary"
                onClick={async () => {
                  await onConfirm({ promote_prompt: promotePrompt, promote_skills: promoteSkills });
                  close();
                }}
                disabled={!promotePrompt && !promoteSkills}
              >
                CONFIRMER
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
