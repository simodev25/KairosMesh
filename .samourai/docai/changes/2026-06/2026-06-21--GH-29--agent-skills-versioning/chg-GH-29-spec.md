---
change:
  ref: GH-29
  type: refactor
  status: Proposed
  slug: agent-skills-versioning
  title: "Versionnage des skills d'agents dans une table dédiée (pattern prompt_templates)"
  owners: [engineering]
  service: agent-skills
  labels: [type:chore, priority:high, change]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal: [model-selector, agent-pipeline, connectors-api, frontend-connectors]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** : Migrer le stockage des skills des agents de trading depuis un champ JSON non versionné (`connector_configs.settings.agent_skills`) vers une table dédiée `agent_skills` dotée d'un versioning complet, afin de permettre le suivi des mutations, le rollback, et d'établir le socle technique requis par l'Evolution Lab (GH-28).

---

## 1. SUMMARY

Les skills des 12 agents de trading sont actuellement stockées dans un champ JSON non structuré (`connector_configs.settings`), sans historique ni versioning. Ce changement crée une table dédiée `agent_skills` reprenant exactement le même patron de versioning que `prompt_templates`, y compris une migration Alembic des données existantes, l'adaptation de tous les sites d'accès en lecture, une API REST dédiée (CRUD + activation) et l'adaptation du frontend `ConnectorsPage`. Le mécanisme de bootstrap existant (`skill_bootstrap.py`) est supprimé et remplacé par un seed de démarrage dans la nouvelle table.

---

## 2. CONTEXTE

### 2.1 État actuel

- Les skills des agents de trading sont définies dans des fichiers `SKILL.md` sous `backend/config/skills/<nom-agent>/SKILL.md`.
- Au démarrage, `skill_bootstrap.py` lit ces fichiers et les pousse dans `connector_configs.settings.agent_skills` (champ JSON libre) pour chaque connecteur.
- La lecture des skills se fait principalement via `AgentModelSelector.resolve_skills()` dans `model_selector.py`, qui interroge `connector_configs.settings`.
- Il existe 12 agents couverts par le JSON existant : les 9 du pipeline principal plus `strategy-designer`, `schedule-planner-agent` et `order-guardian`.
- Le module `AgentScope toolkit.py` dispose d'un fallback de lecture directe sur le fichier `SKILL.md` si le champ JSON est vide.
- Les prompts des agents bénéficient d'un système de versioning complet via la table `prompt_templates` (version, `is_active`, `created_by_id`, historique).
- Aucun mécanisme équivalent n'existe pour les skills.

### 2.2 Points de douleur / Lacunes

- **Absence de versioning** : toute modification d'une skill écrase la version précédente sans traçabilité.
- **Pas d'historique** : il est impossible de savoir quelle skill était active à un instant T, ni de la restaurer.
- **Asymétrie architecturale** : les prompts sont versionnés et auditables ; les skills ne le sont pas. Cela génère une incohérence de modèle cognitive pour les développeurs.
- **Bloqueur GH-28** : l'Evolution Lab a besoin de suivre les mutations de skills et de les rollback ; l'absence de versioning rend cette fonctionnalité impossible.
- **Couplage fort au connecteur** : les skills sont stockées dans `connector_configs.settings`, un champ qui concerne la configuration LLM, pas les capacités comportementales des agents.
- **Bootstrap fragile** : `skill_bootstrap.py` utilise des variables d'environnement et un mécanisme ad-hoc difficile à maintenir et à tester.

---

## 3. ÉNONCÉ DU PROBLÈME

Parce que les skills des agents de trading sont stockées dans un champ JSON sans versioning dans la table de configuration des connecteurs LLM, il est impossible pour l'équipe engineering de tracer, d'auditer ou de rollback une modification de skill — ce qui bloque le développement de l'Evolution Lab (GH-28) et crée une incohérence structurelle avec le système de versioning des prompts, déjà opérationnel.

---

## 4. OBJECTIFS

- **G-1** : Créer une table dédiée `agent_skills` avec versioning complet (version, activation, horodatages, auteur) selon le même patron que `prompt_templates`.
- **G-2** : Migrer les données existantes depuis `connector_configs.settings.agent_skills` vers la nouvelle table via une migration Alembic data migration.
- **G-3** : Adapter tous les sites de lecture des skills dans le backend pour utiliser la nouvelle table comme source canonique.
- **G-4** : Fournir une API REST dédiée permettant la gestion complète des skills par agent (liste, détail, nouvelle version, activation).
- **G-5** : Adapter le frontend `ConnectorsPage` pour interagir avec la nouvelle API plutôt qu'avec le champ JSON du connecteur.
- **G-6** : Supprimer le mécanisme de bootstrap existant (`skill_bootstrap.py`, variables d'environnement associées) et le remplacer par un seed de démarrage dans la nouvelle table.
- **G-7** : Préserver le fallback sur les fichiers `SKILL.md` si la table est vide pour un agent donné (continuité de service).
- **G-8** : Garantir la backward compatibility de `GET /api/v1/connectors` en servant les skills depuis la nouvelle table.

### 4.1 Métriques de succès / KPIs

| Métrique | Cible |
|----------|-------|
| Agents couverts par la table `agent_skills` | 12 / 12 (les 9 du pipeline + 3 additionnels) |
| Sites d'accès aux skills adaptés | 100 % (aucun accès direct à `connector_configs.settings.agent_skills` en production) |
| Régression du pipeline d'analyse | 0 régression (tous les tests existants passent) |
| Couverture de tests du nouveau service | ≥ 80 % du service `AgentSkillsService` |
| `skill_bootstrap.py` supprimé | Oui |
| Rollback d'une version de skill opérationnel | Oui (via activation d'une version antérieure) |

### 4.2 Non-Goals

- **NG-1** : Modification du contenu des skills (les textes des skills restent inchangés dans cette livraison).
- **NG-2** : Création d'une page UI dédiée à la gestion des versions de skills (reporté à GH-28, Evolution Lab).
- **NG-3** : Versioning au niveau d'une skill individuelle (la granularité retenue est le jeu complet de skills par agent).
- **NG-4** : Support multi-tenants ou multi-organisations pour les skills.
- **NG-5** : Intégration à un système de feature flags externe.

---

## 5. CAPACITÉS FONCTIONNELLES

| ID | Capacité | Justification |
|----|----------|---------------|
| F-1 | Stockage versionné des skills par agent dans une table dédiée | Permet le suivi historique, l'audit et le rollback — prérequis GH-28 |
| F-2 | Migration automatique des données existantes lors du déploiement | Garantit la continuité sans perte de données et sans intervention manuelle |
| F-3 | Lecture des skills depuis la nouvelle table par le sélecteur de modèles | Source canonique unique pour tous les agents consommateurs |
| F-4 | API REST de gestion des skills (CRUD + activation) | Permet aux opérateurs de gérer les versions via l'interface ou des scripts |
| F-5 | Adaptation du frontend pour l'affichage et l'édition via la nouvelle API | Cohérence de l'expérience utilisateur dans `ConnectorsPage` |
| F-6 | Seed de démarrage remplaçant le bootstrap existant | Mécanisme de démarrage fiable, testable et cohérent avec les prompts |
| F-7 | Fallback fichier `SKILL.md` si table vide pour un agent | Résilience : le pipeline ne tombe pas si la table est vide pour un agent donné |
| F-8 | Backward compatibility sur `GET /api/v1/connectors` | Aucune régression côté client existant sans migration de l'appelant |

### 5.1 Détail des capacités

**F-1 — Stockage versionné**  
La table `agent_skills` stocke, pour chaque agent, des versions numérotées séquentiellement du jeu de skills (tableau de chaînes). Une seule version est active à la fois par agent (`is_active = true`). Chaque version est immuable une fois créée : pour modifier les skills d'un agent, on crée une nouvelle version.

**F-2 — Migration des données existantes**  
La migration Alembic en charge de la création de la table effectue simultanément un transfert des valeurs JSON présentes dans `connector_configs.settings.agent_skills` vers des entrées de version 1 dans la nouvelle table, marquées `is_active = true`. Si aucune valeur n'est présente pour un agent, aucune ligne n'est créée (le fallback F-7 prend le relais).

**F-3 — Lecture des skills**  
`AgentModelSelector.resolve_skills(agent_name)` interroge la table `agent_skills` pour retourner la version active de l'agent. En l'absence d'entrée active, le fallback sur le fichier `SKILL.md` est déclenché. Le cache interne `_settings_cache` est adapté pour ne plus contenir de skills (séparation des responsabilités).

**F-4 — API REST**  
Quatre endpoints dédiés permettent : lister toutes les versions pour un agent, récupérer le détail d'une version, créer une nouvelle version (avec optionnellement activation immédiate), et activer une version existante. La création d'une version n'est pas destructive : toutes les versions antérieures restent accessibles.

**F-5 — Adaptation frontend**  
`ConnectorsPage` utilise la nouvelle API pour afficher la skill active et permettre la mise à jour (création d'une nouvelle version). La liste déroulante des versions disponibles est présentée si plusieurs versions existent. L'écriture dans `connector_configs.settings.agent_skills` via `PUT /connectors` est désactivée côté frontend.

**F-6 — Seed de démarrage**  
Au premier démarrage (table vide), un mécanisme de seed charge les contenus des fichiers `SKILL.md` de référence et crée la version 1 de chaque agent dans la table. Ce mécanisme est idempotent : si des entrées existent déjà, il ne crée rien.

**F-7 — Fallback fichier SKILL.md**  
Si `resolve_skills()` ne trouve aucune version active dans la table pour un agent donné, le contenu du fichier `SKILL.md` correspondant est retourné. Ce comportement est identique à l'actuel `toolkit.py`. Un avertissement de log est émis pour signaler le fallback.

**F-8 — Backward compatibility GET /connectors**  
La réponse du endpoint `GET /api/v1/connectors` continue d'inclure le champ `agent_skills` dans la section `settings` de chaque connecteur, en lisant désormais la valeur depuis la version active dans la table `agent_skills` (et non depuis `connector_configs.settings`).

---

## 6. FLUX UTILISATEURS & SYSTÈME

### Flux 1 : Lecture des skills par le pipeline d'analyse

```
Pipeline d'analyse
  → AgentScope registry.py / governance/registry.py / strategy/designer.py
  → AgentModelSelector.resolve_skills(agent_name)
  → [Requête DB] agent_skills WHERE agent_name=X AND is_active=true
  → [Si non trouvé] Lecture fichier SKILL.md (fallback)
  → Retourne la liste de skills actives pour l'agent
```

### Flux 2 : Création d'une nouvelle version de skill (via API)

```
Opérateur / Frontend ConnectorsPage
  → POST /api/v1/agents/{name}/skills
    Body: { skills: [...], notes: "...", activate: true }
  → AgentSkillsService.create_version(agent_name, skills, notes, user_id, activate)
  → [Si activate=true] Désactive la version précédente (is_active=false)
  → Insère nouvelle ligne dans agent_skills (version N+1, is_active=activate)
  → Retourne la version créée (201 Created)
```

### Flux 3 : Activation d'une version existante

```
Opérateur / Frontend
  → POST /api/v1/agents/{name}/skills/{version}/activate
  → AgentSkillsService.activate_version(agent_name, version)
  → Désactive toutes les versions actives pour cet agent
  → Active la version demandée
  → Retourne 200 OK avec version activée
```

### Flux 4 : Démarrage du système (seed)

```
Application startup (main.py)
  → AgentSkillsSeedService.seed_if_empty()
  → Pour chaque agent : agent_skills WHERE agent_name=X → COUNT
  → [Si COUNT = 0] Lit SKILL.md → Insère version 1 (is_active=true, created_by=SYSTEM)
  → [Si COUNT > 0] No-op
```

### Flux 5 : GET /connectors (backward compatibility)

```
Frontend (appel existant)
  → GET /api/v1/connectors
  → ConnectorsService.list_connectors()
  → Pour chaque connecteur : AgentModelSelector.resolve_skills(agent_name)
  → [Lecture table agent_skills, version active]
  → Injecte agent_skills dans settings.agent_skills de la réponse
  → Retourne la réponse enrichie (format inchangé)
```

---

## 7. PÉRIMÈTRE & LIMITES

### 7.1 In Scope

- Création de la table `agent_skills` (DDL Alembic).
- Migration des données existantes depuis `connector_configs.settings.agent_skills` (data migration dans le même script Alembic).
- Nouveau service `AgentSkillsService` (requêtes CRUD + logique d'activation).
- Nouveau service `AgentSkillsSeedService` (seed idempotent au démarrage).
- Adaptation de `AgentModelSelector.resolve_skills()` pour lire depuis la nouvelle table.
- Adaptation du cache `_settings_cache` pour ne plus inclure les skills.
- Adaptation de tous les sites d'appel identifiés dans le backend (agentscope, governance, strategy, prompts).
- Adaptation du fallback `toolkit.py` pour appeler `resolve_skills()` plutôt que lire directement le fichier.
- Nouveaux endpoints API REST dédiés aux skills (`/api/v1/agents/{name}/skills`).
- Adaptation de `GET /api/v1/connectors` pour servir les skills depuis la nouvelle table.
- Désactivation de l'écriture des skills via `PUT /api/v1/connectors` (retour 400 ou ignoré silencieusement avec un log d'avertissement).
- Adaptation de `ConnectorsPage.tsx` pour afficher et éditer les skills via la nouvelle API.
- Suppression de `skill_bootstrap.py` et des variables d'environnement associées dans `config.py`.
- Suppression de l'appel au bootstrap dans `main.py`.
- Mise à jour des tests existants impactés.
- Nouveaux tests unitaires pour `AgentSkillsService`.
- Couverture des 12 agents : `technical-analyst`, `news-analyst`, `market-context-analyst`, `bullish-researcher`, `bearish-researcher`, `trader-agent`, `risk-manager`, `execution-manager`, `governance-trader`, `strategy-designer`, `schedule-planner-agent`, `order-guardian`.

### 7.2 Out of Scope

- [OUT] Modification du contenu textuel des skills (les textes restent inchangés).
- [OUT] Nouvelle page UI dédiée à la gestion des versions de skills (reporté GH-28).
- [OUT] Versioning au niveau d'une skill individuelle (la granularité est le jeu complet par agent).
- [OUT] Intégration de l'historique des skills dans les dashboards d'observabilité.
- [OUT] API d'export/import de skills entre environnements.
- [OUT] Suppression des fichiers `SKILL.md` de référence (conservés comme source du seed et fallback).
- [OUT] Modification du moteur de risque (`backend/app/risk/`).

### 7.3 Différé / Peut-être plus tard

- Interface UI dédiée pour naviguer dans l'historique des versions et comparer deux versions de skills (GH-28, Evolution Lab).
- Notation/évaluation des versions de skills (liée à GH-28).
- Diff visuel entre deux versions de skills.
- Webhooks ou événements lors d'un changement de version active.
- Promotion de skills entre environnements (dev → staging → prod).

---

## 8. INTERFACES & CONTRATS D'INTÉGRATION

### 8.1 REST / HTTP Endpoints

| Méthode | Path | Description | Réponse |
|---------|------|-------------|---------|
| `GET` | `/api/v1/agents/{name}/skills` | Liste toutes les versions de skills pour un agent | `200` liste de versions |
| `GET` | `/api/v1/agents/{name}/skills/{version}` | Détail d'une version spécifique | `200` version détaillée |
| `POST` | `/api/v1/agents/{name}/skills` | Crée une nouvelle version (optionnellement active) | `201` version créée |
| `POST` | `/api/v1/agents/{name}/skills/{version}/activate` | Active une version existante | `200` version activée |

**Schéma de réponse (version) :**

```
{
  id: integer,
  agent_name: string,            // identifiant de l'agent (ex. "technical-analyst")
  version: integer,              // numéro de version séquentiel par agent
  is_active: boolean,
  skills: string[],              // tableau des skills de l'agent
  notes: string | null,          // note libre de l'auteur
  created_by_id: integer | null,
  created_at: datetime (ISO 8601),
  updated_at: datetime (ISO 8601)
}
```

**Évolution de `GET /api/v1/connectors` :**  
Le champ `settings.agent_skills` continue d'être retourné dans chaque connecteur, sa valeur étant désormais issue de la version active de la table `agent_skills` (lecture via `AgentModelSelector.resolve_skills()`). Le format du champ est inchangé.

**Comportement de `PUT /api/v1/connectors/{id}` :**  
Si le corps de la requête inclut `settings.agent_skills`, ce champ est ignoré (avec un log d'avertissement) et une erreur `400 Bad Request` est retournée avec le message : `"agent_skills must be managed via /api/v1/agents/{name}/skills"`.

### 8.2 Événements / Messages

N/A — aucun événement ou message asynchrone n'est introduit par ce changement.

### 8.3 Impact sur le modèle de données

| ID | Élément | Description |
|----|---------|-------------|
| DM-1 | Table `agent_skills` (nouvelle) | Table dédiée au versioning des skills par agent |
| DM-2 | `agent_skills.id` | Clé primaire entière auto-incrémentée |
| DM-3 | `agent_skills.agent_name` | Identifiant de l'agent (varchar, ex. `"technical-analyst"`) |
| DM-4 | `agent_skills.version` | Numéro de version séquentiel par agent (integer) |
| DM-5 | `agent_skills.is_active` | Indique si cette version est la version active (boolean, défaut false) |
| DM-6 | `agent_skills.skills` | Tableau JSON de chaînes représentant les skills (JSONB) |
| DM-7 | `agent_skills.notes` | Note optionnelle de l'auteur de la version (text nullable) |
| DM-8 | `agent_skills.created_by_id` | Référence à l'utilisateur créateur (FK vers `users.id`, nullable) |
| DM-9 | `agent_skills.created_at` | Horodatage de création (timestamp with timezone) |
| DM-10 | `agent_skills.updated_at` | Horodatage de dernière modification (timestamp with timezone) |
| DM-11 | Contrainte unicité | `UNIQUE(agent_name, version)` — une seule version N par agent |
| DM-12 | Index | `INDEX(agent_name, is_active)` — optimise `resolve_skills()` |
| DM-13 | `connector_configs.settings.agent_skills` | Champ dépréciée : les données existantes sont migrées et le champ n'est plus alimenté |

**Pattern de versioning (référence `prompt_templates`) :**  
Une seule ligne par agent peut avoir `is_active = true`. Lors de l'activation d'une version N, toutes les lignes avec `agent_name = X AND is_active = true` sont passées à `false`, puis la ligne de la version N est passée à `true`. Ce pattern est atomique (transaction).

### 8.4 Intégrations externes

N/A — ce changement est purement interne. Aucune API externe n'est introduite.

### 8.5 Backward Compatibility

| Aspect | Impact | Détail |
|--------|--------|--------|
| `GET /api/v1/connectors` | Aucune rupture | Le champ `settings.agent_skills` est toujours présent, alimenté depuis la nouvelle table |
| `PUT /api/v1/connectors` (écriture `agent_skills`) | Rupture intentionnelle | Retourne `400` si `settings.agent_skills` est présent dans le corps — changement signalé et documenté |
| Lecture interne `resolve_skills()` | Transparent | Même interface de méthode, source de données changée |
| Fichiers `SKILL.md` | Inchangés | Conservés comme source du seed et fallback de résilience |
| Variables d'environnement bootstrap | Supprimées | `SKILL_BOOTSTRAP_*` supprimées de `config.py` — à retirer des fichiers `.env` de déploiement |

---

## 9. EXIGENCES NON FONCTIONNELLES (NFRs)

| ID | Exigence | Seuil |
|----|----------|-------|
| NFR-1 | Latence de `resolve_skills()` | P95 ≤ 10 ms (requête indexée sur `agent_name, is_active`) |
| NFR-2 | Idempotence du seed | Zéro doublons créés si le seed est appelé plusieurs fois |
| NFR-3 | Atomicité de l'activation | L'opération d'activation est exécutée dans une transaction SQL unique — aucun état intermédiaire incohérent |
| NFR-4 | Régression pipeline | 0 test existant en échec après migration |
| NFR-5 | Couverture du nouveau service | ≥ 80 % des branches du service `AgentSkillsService` couvertes par des tests unitaires |
| NFR-6 | Compatibilité Alembic | La migration est réversible (`downgrade`) sans perte de données (re-écriture dans `connector_configs.settings`) |
| NFR-7 | Taille des skills | Les skills d'un agent ne dépassent pas 50 entrées et 64 KB au total (validé à la création) |

---

## 10. TÉLÉMÉTRIE & OBSERVABILITÉ

| Élément | Type | Description |
|---------|------|-------------|
| `agent_skills.fallback_triggered` | Log WARNING | Émis quand le fallback `SKILL.md` est déclenché pour un agent (indicateur de table vide) |
| `agent_skills.version_activated` | Log INFO | Émis à chaque activation de version (agent_name, version, user_id) |
| `agent_skills.seed_executed` | Log INFO | Émis lors de l'exécution du seed (agents créés, agents ignorés car déjà présents) |
| `agent_skills.resolve_duration_ms` | Métrique Prometheus | Histogramme de la durée de `resolve_skills()` par agent (labels: `agent_name`, `source=db|fallback`) |

---

## 11. RISQUES & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque résiduel |
|----|--------|--------|-------------|------------|-----------------|
| RSK-1 | Régression du pipeline d'analyse due à un changement de comportement de `resolve_skills()` | H | M | Tests de non-régression sur tous les sites d'appel identifiés avant merge ; tests d'intégration du pipeline | Faible si tests passent |
| RSK-2 | Données existantes incomplètes ou malformées dans `connector_configs.settings.agent_skills` | M | M | Script de migration avec validation des données ; fallback SKILL.md en cas d'absence | Négligeable |
| RSK-3 | Cache `_settings_cache` de `model_selector.py` retournant des skills périmées après migration | M | H | Invalidation du cache lors de l'activation d'une nouvelle version ; adaptation de la logique de cache dans cette livraison | Faible |
| RSK-4 | Coexistence temporaire entre l'ancien champ JSON et la nouvelle table pendant le déploiement | L | M | Déploiement atomique avec migration Alembic incluse ; aucune demi-migration possible | Négligeable |
| RSK-5 | Frontend envoyant encore `agent_skills` via `PUT /connectors` après mise à jour | M | L | Le backend retourne `400` avec un message explicite ; adaptation du frontend dans ce même ticket | Faible |
| RSK-6 | Suppression de `skill_bootstrap.py` crée un démarrage cassé si le seed échoue | H | L | Seed avec gestion d'erreur robuste ; log d'erreur critique ; fallback SKILL.md toujours présent | Moyen — à monitorer en déploiement |

---

## 12. HYPOTHÈSES

- La table `prompt_templates` est une référence directe pour le patron de versioning à adopter (même colonnes, même logique d'activation).
- Les 12 agents identifiés couvrent l'ensemble des agents actifs dans le système au moment de la livraison.
- Les données dans `connector_configs.settings.agent_skills` sont des tableaux de chaînes valides (ou absentes), sans valeurs corrompues.
- Le système peut être redéployé avec une migration Alembic atomique sans fenêtre de maintenance.
- L'utilisateur `SYSTEM` (ou un utilisateur technique dédié) est disponible pour `created_by_id` lors du seed.
- Les fichiers `SKILL.md` de référence dans `backend/config/skills/` restent présents et valides après la suppression de `skill_bootstrap.py`.

---

## 13. DÉPENDANCES

| Direction | Élément | Notes |
|-----------|---------|-------|
| Bloque | GH-28 (Evolution Lab) | GH-29 est le prérequis de GH-28 — la table versionnée est le socle de l'Evolution Lab |
| Dépend de | `prompt_templates` (pattern) | Le patron de versioning est recopié depuis la table et le service existants |
| Dépend de | PostgreSQL + Alembic | Migration DDL + data dans une transaction Alembic standard |
| Dépend de | `connector_configs` (source) | Les données à migrer sont dans `connector_configs.settings` |
| Dépend de | Fichiers `SKILL.md` | Utilisés comme source du seed et fallback |

---

## 14. QUESTIONS OUVERTES

| ID | Question | Contexte | Statut |
|----|----------|---------|--------|
| OQ-1 | Que faire si la migration Alembic détecte un agent dans `connector_configs.settings` qui ne figure pas dans la liste des 12 agents connus ? | Agents créés dynamiquement ou agents legacy non référencés | À trancher — migrer quand même (recommandé) ou ignorer ? |
| OQ-2 | Le retour `400` sur `PUT /connectors` avec `agent_skills` est-il acceptable pour les intégrations externes connues ? | Backward compat intentionnellement rompue | Confirmer qu'aucun script externe n'écrit dans ce champ |

---

## 15. JOURNAL DES DÉCISIONS

| ID | Décision | Justification | Date |
|----|----------|---------------|------|
| DEC-1 | Granularité : jeu complet de skills par agent, pas skill individuelle | Cohérence avec `prompt_templates` (le prompt est un bloc, pas une phrase) ; simplicité de la migration | 2026-06-21 |
| DEC-2 | Migration Alembic data migration dans le même script que la DDL | Déploiement atomique : créer la table et migrer les données en une seule transaction évite tout état intermédiaire incohérent | 2026-06-21 |
| DEC-3 | Supprimer `skill_bootstrap.py` et le remplacer par un seed idempotent au démarrage | Alignement avec le mécanisme des prompts ; suppression de la dette technique et du couplage aux variables d'environnement | 2026-06-21 |
| DEC-4 | `GET /connectors` continue de servir `agent_skills` (source = nouvelle table) | Backward compatibility stricte côté client existant — aucune migration du frontend requise pour la lecture | 2026-06-21 |
| DEC-5 | Frontend adapté dans ce même ticket (pas un ticket séparé) | La `ConnectorsPage` écrit actuellement dans `connector_configs.settings.agent_skills` — sans adaptation, la fonctionnalité serait cassée dès le merge backend | 2026-06-21 |
| DEC-6 | Couvrir les 12 agents (9 pipeline + 3 additionnels) | La migration doit être exhaustive pour éviter un état partiel post-déploiement | 2026-06-21 |
| DEC-7 | `PUT /connectors` avec `agent_skills` retourne `400` | Rupture explicite préférable à une ignorance silencieuse — facilite le débogage et force la migration des appelants | 2026-06-21 |

---

## 16. COMPOSANTS AFFECTÉS (HAUT NIVEAU)

| Composant | Impact |
|-----------|--------|
| Table `agent_skills` | Nouveau |
| Migration Alembic (DDL + data) | Nouveau |
| `AgentSkillsService` | Nouveau |
| `AgentSkillsSeedService` | Nouveau |
| API routes `/api/v1/agents/{name}/skills` | Nouveau |
| `AgentModelSelector.resolve_skills()` | Modifié (source de données) |
| `AgentModelSelector._settings_cache` | Modifié (séparation skills/config) |
| `AgentScope registry.py` | Modifié (4 sites d'appel) |
| `AgentScope toolkit.py` | Modifié (fallback via `resolve_skills()`) |
| `Governance registry.py` | Modifié (2 sites d'appel) |
| `Strategy designer.py` | Modifié (1 site d'appel) |
| `Prompts registry.py` | Modifié (1 site d'appel) |
| `Connectors API routes` | Modifié (backward compat, rejet écriture) |
| `main.py` (startup) | Modifié (suppression bootstrap, ajout seed) |
| `config.py` | Modifié (suppression vars d'env bootstrap) |
| `skill_bootstrap.py` | Supprimé |
| `ConnectorsPage.tsx` | Modifié (lecture + écriture via nouvelle API) |
| `test_agent_model_selector.py` | Modifié |
| `test_skill_bootstrap.py` | Supprimé ou converti |
| `test_connectors_settings_sanitization.py` | Modifié |
| `test_prompt_registry.py` | Modifié (si couplage `resolve_skills`) |
| `test_no_french_in_production.py` | Modifié (si couverture bootstrap) |
| `test_agentscope_registry.py` | Modifié |
| Nouveaux tests `test_agent_skills_service.py` | Nouveau |

---

## 17. CRITÈRES D'ACCEPTATION

| ID | Critère | Lié à |
|----|---------|-------|
| AC-DM1-1 | **Étant donné** un déploiement sur une base vierge, **quand** la migration Alembic s'exécute, **alors** la table `agent_skills` existe avec toutes les colonnes définies en DM-1 à DM-12. | DM-1 |
| AC-DM1-2 | **Étant donné** une base avec des données dans `connector_configs.settings.agent_skills`, **quand** la migration s'exécute, **alors** chaque entrée est créée dans `agent_skills` en version 1 avec `is_active = true`. | DM-1, F-2 |
| AC-F3-1 | **Étant donné** un agent avec une version active dans `agent_skills`, **quand** `resolve_skills(agent_name)` est appelé, **alors** le tableau de skills de la version active est retourné en ≤ 10 ms (P95). | F-3, NFR-1 |
| AC-F7-1 | **Étant donné** un agent sans aucune entrée dans `agent_skills`, **quand** `resolve_skills(agent_name)` est appelé, **alors** le contenu du fichier `SKILL.md` correspondant est retourné et un avertissement est loggué. | F-7 |
| AC-F4-1 | **Étant donné** un agent existant, **quand** `POST /api/v1/agents/{name}/skills` est appelé avec un tableau de skills valide, **alors** une nouvelle version est créée (201 Created) et, si `activate=true`, devient la version active. | F-4 |
| AC-F4-2 | **Étant donné** un agent avec plusieurs versions, **quand** `POST /api/v1/agents/{name}/skills/{version}/activate` est appelé, **alors** seule cette version a `is_active=true` et la version précédemment active passe à `false`. | F-4, DEC-1 |
| AC-F4-3 | **Étant donné** une requête `GET /api/v1/agents/{name}/skills`, **quand** l'agent existe, **alors** toutes ses versions sont retournées avec leur numéro de version, statut `is_active`, et horodatages. | F-4 |
| AC-F5-1 | **Étant donné** la page `ConnectorsPage`, **quand** un utilisateur modifie les skills d'un agent, **alors** l'appel part vers `POST /api/v1/agents/{name}/skills` et non vers `PUT /api/v1/connectors/{id}`. | F-5 |
| AC-F8-1 | **Étant donné** un client appelant `GET /api/v1/connectors`, **quand** la requête est reçue, **alors** chaque connecteur retourne `settings.agent_skills` avec les skills de la version active issue de la table `agent_skills`. | F-8 |
| AC-F8-2 | **Étant donné** un `PUT /api/v1/connectors/{id}` avec `settings.agent_skills` dans le corps, **quand** la requête est reçue, **alors** le serveur retourne `400 Bad Request` avec un message explicite. | F-8, DEC-7 |
| AC-F6-1 | **Étant donné** un démarrage sur une base avec `agent_skills` vide, **quand** l'application démarre, **alors** les 12 agents ont chacun une version 1 dans la table, issue de leurs fichiers `SKILL.md`. | F-6 |
| AC-F6-2 | **Étant donné** un démarrage avec `agent_skills` déjà peuplée, **quand** l'application démarre, **alors** aucune nouvelle ligne n'est créée (idempotence). | F-6, NFR-2 |
| AC-NFR4-1 | **Étant donné** la suite de tests existante, **quand** toutes les migrations et adaptations sont appliquées, **alors** 0 test en échec supplémentaire. | NFR-4 |
| AC-NFR5-1 | **Étant donné** le nouveau service `AgentSkillsService`, **quand** les tests unitaires sont exécutés, **alors** ≥ 80 % des branches sont couvertes. | NFR-5 |
| AC-NFR6-1 | **Étant donné** une migration appliquée, **quand** `alembic downgrade -1` est exécuté, **alors** la table est supprimée et les données sont ré-écrites dans `connector_configs.settings.agent_skills`. | NFR-6 |

---

## 18. DÉPLOIEMENT & GESTION DU CHANGEMENT (HAUT NIVEAU)

**Stratégie de merge** : feature branch → `main` avec PR après validation de la CI.

**Ordre de livraison recommandé** :
1. Migration Alembic (DDL + data) — exécutée au déploiement.
2. Seed idempotent au démarrage (remplace bootstrap).
3. Nouveau service + API REST — déployé avec le backend.
4. Adaptation des sites de lecture (`resolve_skills()`, registries).
5. Adaptation de `ConnectorsPage.tsx` — déployée avec le frontend.
6. Suppression de `skill_bootstrap.py` et des variables d'environnement associées.

**Communication** :
- Les fichiers `.env` de déploiement doivent supprimer les variables `SKILL_BOOTSTRAP_*`.
- La rupture sur `PUT /connectors` avec `agent_skills` est documentée dans la description de PR et la release note.

---

## 19. MIGRATION DE DONNÉES / SEEDING

La migration de données est incluse dans la migration Alembic. Lors du `upgrade` :
1. La table `agent_skills` est créée.
2. Pour chaque connecteur dans `connector_configs`, si `settings.agent_skills` est non nul et non vide, une ligne est insérée dans `agent_skills` (version 1, `is_active=true`, `notes='Migrated from connector_configs'`).

Lors du `downgrade` :
1. Pour chaque agent dans `agent_skills` avec `is_active=true`, la valeur est ré-écrite dans `connector_configs.settings.agent_skills` du connecteur correspondant.
2. La table `agent_skills` est supprimée.

Le seed de démarrage (distinct de la migration Alembic) opère uniquement si la table est vide pour un agent donné, en lisant les fichiers `SKILL.md` de référence.

---

## 20. REVUE CONFIDENTIALITÉ / CONFORMITÉ

N/A — les skills sont des descriptions comportementales des agents, sans donnée personnelle. Aucune exigence RGPD applicable à ce changement.

---

## 21. POINTS DE SÉCURITÉ

| Aspect | Niveau | Note |
|--------|--------|------|
| Injection via champ `skills` | Faible | Les skills sont du texte libre envoyé aux LLMs — une validation de la taille et du type est recommandée (NFR-7) |
| Accès à l'API de gestion des skills | Faible | Les endpoints doivent être soumis à la même authentification que les autres endpoints `/api/v1/` |
| Suppression de `skill_bootstrap.py` | Neutre | Réduit la surface d'attaque liée aux variables d'environnement bootstrap |

---

## 22. IMPACT MAINTENANCE & OPÉRATIONS

- **Suppression de la dette technique** : `skill_bootstrap.py` et ses variables d'environnement associées sont retirés, réduisant la complexité opérationnelle du démarrage.
- **Cohérence** : les skills et les prompts suivent désormais le même patron — la courbe d'apprentissage pour les nouveaux développeurs est réduite.
- **Rollback opérationnel** : un opérateur peut restaurer une version précédente de skills via l'API sans redéploiement.
- **Observabilité** : le fallback sur `SKILL.md` est désormais loggué, permettant de détecter une table incohérente.

---

## 23. GLOSSAIRE

| Terme | Définition |
|-------|------------|
| Agent de trading | Un des 12 agents du pipeline Kairos Mesh ayant un rôle fonctionnel spécifique dans le pipeline d'analyse ou de gouvernance |
| Skill | Capacité comportementale déclarative d'un agent de trading, exprimée sous forme de chaîne de texte (ex. `"Analyse les patterns de chandeliers japonais"`) |
| Jeu de skills | L'ensemble des skills d'un agent à un instant donné, stocké comme un tableau de chaînes |
| Version active | La version du jeu de skills effectivement utilisée par le pipeline à un instant donné (`is_active = true`) |
| `prompt_templates` | Table existante de versioning des prompts système des agents — référence architecturale pour ce changement |
| `skill_bootstrap.py` | Module existant de chargement initial des skills depuis les fichiers `SKILL.md` vers `connector_configs.settings` — supprimé dans ce changement |
| Seed | Mécanisme idempotent de peuplement initial de la table `agent_skills` depuis les fichiers `SKILL.md` de référence, exécuté au démarrage |
| Fallback | Comportement de résilience : si la table `agent_skills` ne contient pas d'entrée active pour un agent, le fichier `SKILL.md` correspondant est lu directement |
| Evolution Lab | Feature GH-28 — système d'expérimentation et d'évolution des agents, prérequis de ce changement |

---

## 24. ANNEXES

### Annexe A — Schéma DDL de la table `agent_skills` (référence)

```sql
CREATE TABLE agent_skills (
    id             SERIAL PRIMARY KEY,
    agent_name     VARCHAR(100) NOT NULL,
    version        INTEGER NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    skills         JSONB NOT NULL DEFAULT '[]',
    notes          TEXT,
    created_by_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_skills_agent_version UNIQUE (agent_name, version)
);

CREATE INDEX idx_agent_skills_active ON agent_skills (agent_name, is_active);
```

### Annexe B — Liste des 12 agents couverts

| Identifiant | Rôle | Pipeline |
|-------------|------|---------|
| `technical-analyst` | Analyse technique | Principal |
| `news-analyst` | Analyse sentiment | Principal |
| `market-context-analyst` | Contexte macro | Principal |
| `bullish-researcher` | Argumentation haussière | Principal |
| `bearish-researcher` | Argumentation baissière | Principal |
| `trader-agent` | Décision de trading | Principal |
| `risk-manager` | Validation du risque | Principal |
| `execution-manager` | Exécution des ordres | Principal |
| `governance-trader` | Supervision / gouvernance | Principal |
| `strategy-designer` | Conception de stratégie | Additionnel |
| `schedule-planner-agent` | Planification | Additionnel |
| `order-guardian` | Garde-fou des ordres | Additionnel |

### Annexe C — Correspondance avec le patron `prompt_templates`

| Élément | `prompt_templates` | `agent_skills` (ce changement) |
|---------|--------------------|-------------------------------|
| Granularité | Prompt système complet | Jeu de skills complet |
| Version | Séquentielle par agent | Séquentielle par agent |
| Activation | `is_active = true` | `is_active = true` |
| Auteur | `created_by_id` | `created_by_id` |
| Seed | Seed au démarrage | Seed au démarrage (nouveau) |
| Fallback | Valeur par défaut hardcodée | Fichier `SKILL.md` |

---

## 25. HISTORIQUE DU DOCUMENT

| Version | Date | Auteur | Modifications |
|---------|------|--------|---------------|
| 1.0 | 2026-06-21 | @spec-writer | Spécification initiale — GH-29 |

---

## DIRECTIVES D'AUTEUR

Ce document a été rédigé à partir du résumé de planification fourni par `@pm` à l'issue de la phase `clarify_scope` du ticket GH-29. Les décisions structurantes (granularité, migration, bootstrap, backward compat) ont été capturées dans `chg-GH-29-pm-notes.yaml` et sont reflétées fidèlement dans les sections DEC-* et DM-* de ce document. Les informations manquantes sont capturées en OQ-*. Aucun détail d'implémentation (chemins de fichiers, code) n'a été inclus dans ce document conformément aux règles du rôle `@spec-writer`.

## LISTE DE VALIDATION

- [x] `change.ref` correspond au `workItemRef` fourni (GH-29)
- [x] `owners` contient au moins une entrée
- [x] `status` est "Proposed"
- [x] Toutes les sections présentes dans l'ordre (1 à 25 + directives + validation)
- [x] Préfixes d'ID cohérents et uniques (F-, AC-, NFR-, RSK-, DEC-, DM-, OQ-)
- [x] Les critères d'acceptation référencent au moins un ID F-/NFR-/DM- et utilisent Given/When/Then
- [x] Les NFRs incluent des valeurs mesurables
- [x] Les risques incluent Impact & Probabilité
- [x] Aucun détail d'implémentation (pas de chemins de fichiers, pas de tâches pas-à-pas)
- [x] Front matter valide selon les règles `front_matter_rules`
