# PM Instructions — Kairos Mesh

> **Langue :** Tous les messages, tickets, et artefacts sont rédigés en **français**.

Ce fichier contient la configuration spécifique au projet pour l'agent `@pm`.
Le cycle de delivery standard ADOS est documenté dans `doc/guides/change-lifecycle.md`.

---

## 1. Configuration du tracker

| Paramètre | Valeur |
|-----------|--------|
| Type | GitHub Issues |
| Repo | `simodev25/MultiAgentTrading` |
| Accès | `gh` CLI |
| Format workItemRef | `GH-<number>` (ex. `GH-42`) |

---

## 2. Mapping des états workflow

| Phase ADOS | Label GitHub | Action |
|------------|-------------|--------|
| Backlog | _(pas de label)_ | Issue ouverte, non assignée |
| In Progress | `in-progress` | Issue assignée, branch créée |
| Review | `review` | PR ouverte, issue liée |
| Blocked | `blocked` | Commentaire + label |
| Delivered | `delivered` | Issue fermée après merge |

---

## 3. Taxonomie des labels

| Label | Usage |
|-------|-------|
| `change` | Ticket de changement ADOS (obligatoire sur tout ticket de delivery) |
| `in-progress` | Travail en cours |
| `review` | En attente de review / PR ouverte |
| `blocked` | Bloqué — préciser la raison en commentaire |
| `delivered` | Livré et mergé |
| `bug` | Correctif |
| `feature` | Nouvelle fonctionnalité |
| `governance` | Impact sur le moteur de risque ou la couche d'exécution |
| `agents` | Impact sur un ou plusieurs agents IA du pipeline |

---

## 4. Source de vérité du backlog

Le backlog principal est dans **GitHub Issues** (`simodev25/MultiAgentTrading`).
Les issues labelisées `change` constituent la queue de delivery.

---

## 5. Conventions

- **Branch naming :** `chg/<workItemRef>/<slug>` (ex. `chg/GH-42/governance-risk-cap`)
- **workItemRef :** `GH-<number>` extrait du numéro d'issue GitHub
- **Lien PR → Issue :** inclure `Closes #<number>` dans le corps de la PR

---

## 6. Checklist de validation d'un ticket

Avant de démarrer le cycle sur une issue, vérifier :

- [ ] Description fonctionnelle présente (quoi + pourquoi)
- [ ] Critères d'acceptation listés
- [ ] Impact sur le moteur de risque ou la couche d'exécution identifié (`governance` label si oui)
- [ ] Impact sur les agents IA identifié (`agents` label si oui)
- [ ] Mode concerné précisé : simulation / paper / live

---

## 7. Quality gates projet

Les gates suivants doivent passer avant tout merge :

```bash
# Backend — tests unitaires et intégration
cd backend && pytest

# Frontend — build de production
cd frontend && npm run build
```

En cas d'échec, déléguer à `@runner` puis `@fixer`.

---

## 8. Règles spécifiques au domaine

- Tout changement touchant `backend/app/services/risk_engine*` ou `backend/app/services/execution*`
  requiert une revue de `@architect` avant implémentation.
- Le flag `ALLOW_LIVE_TRADING` ne doit jamais passer à `true` dans les tests ou CI.
- Les agents IA sont dans `backend/app/agents/` — tout changement de prompt ou de logique
  d'agent doit être spécifié dans un artefact `chg-<workItemRef>-spec.md` dédié.
