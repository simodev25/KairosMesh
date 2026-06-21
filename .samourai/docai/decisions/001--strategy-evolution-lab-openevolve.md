---
id: ADR-001
status: draft
date: 2026-06-21
deciders: [simodev25]
---

# ADR-001 — Introduire un Strategy Evolution Lab offline basé sur OpenEvolve

## Statut
draft

## Contexte

Kairos Mesh dispose déjà d'un Strategy Engine, d'un Backtest Engine, d'un monitoring de stratégies et d'un système de benchmark récemment livré. Le produit sait donc déjà générer, valider, monitorer et promouvoir des stratégies, avec une séparation claire entre recherche et exécution.

Le besoin actuel n'est pas d'automatiser davantage le trading live, mais d'améliorer la qualité et la diversité des stratégies candidates produites par le système, en particulier sur trois surfaces :

- les prompts des agents de stratégie et de décision (`strategy-designer`, `trader-agent`, `bullish-researcher`, `bearish-researcher`),
- les paramètres et templates de stratégies,
- à terme, du code de stratégie sandboxé, hors du chemin critique.

OpenEvolve apporte un cadre pertinent pour ce besoin : évolution pilotée par LLM, MAP-Elites / quality-diversity, populations en îles, optimisation multi-objectifs, et boucle de feedback par artefacts.

Contraintes structurantes du système :

- le pipeline de décision live en 4 phases (Analyse → Débat → Décision → Gouvernance) ne doit pas être déstabilisé,
- le moteur de risque déterministe est une zone critique et **ne sera pas impacté**,
- le trading live doit rester isolé de tout mécanisme exploratoire ou auto-évolutif,
- les promotions vers `PAPER` ou `LIVE` doivent rester manuelles et auditables.

Les drivers principaux sont donc :

- augmenter la qualité et la robustesse OOS des stratégies candidates,
- augmenter la diversité des approches explorées,
- préserver l'isolation du live trading,
- limiter le couplage avec le pipeline temps réel,
- conserver une gouvernance humaine forte sur la promotion.

## Options considérées
1. ALT-0 — Ne pas intégrer (statu quo)
2. ALT-1 — Prompt evolution only (offline)
3. ALT-2 — Strategy Evolution Lab découplé (RECOMMANDÉ)
4. ALT-3 — Intégration forte dans le pipeline

## Décision
Option ALT-2 retenue.

## Justification

### Pourquoi ALT-2

ALT-2 introduit un **lab d'évolution offline, découplé du pipeline live**, consommant des snapshots de marché, prompts versionnés, templates de stratégie et évaluations par backtests multi-fenêtres. Cette option maximise l'apprentissage sans contaminer le chemin d'exécution critique.

Le lab exécute OpenEvolve comme service/job séparé, avec son propre stockage d'artefacts et sa propre cadence d'exploration. Il produit des **candidats versionnés** et des rapports d'évaluation, mais ne modifie jamais directement les prompts ni les stratégies actives en production.

### Comparatif synthétique

- **ALT-0**
  - Avantage : zéro risque d'intégration.
  - Limite : aucune amélioration systématique de la recherche de stratégies.

- **ALT-1**
  - Avantage : périmètre réduit, faible coût initial.
  - Limite : n'optimise qu'une partie du problème ; ignore les paramètres/templates et réduit la valeur de MAP-Elites.

- **ALT-2**
  - Avantage : bon équilibre entre capacité d'exploration, isolation opérationnelle, auditabilité et montée en charge progressive.
  - Limite : nécessite une couche d'orchestration offline, un schéma de versionning des candidats et une discipline d'évaluation.

- **ALT-3**
  - Avantage : boucle potentiellement plus rapide entre évolution et exploitation.
  - Limite : couplage fort avec le pipeline live, risque de dérive opérationnelle, complexité de rollback plus élevée, frontière de confiance dégradée.

### Drivers de décision couverts par ALT-2

1. **Sécurité opérationnelle** — le lab reste hors du chemin live.
2. **Préservation des frontières critiques** — aucun impact direct sur `backend/app/services/risk/` ni sur la couche d'exécution broker.
3. **Qualité de recherche** — OpenEvolve peut optimiser plusieurs objectifs simultanément et explorer des niches non triviales.
4. **Auditabilité** — chaque candidat peut être tracé à ses prompts, paramètres, jeux de fenêtres et scores.
5. **Évolutivité** — l'évolution de prompts peut commencer seule, puis s'étendre aux templates/paramètres, puis au code sandboxé.
6. **Réversibilité** — désactiver le lab n'affecte pas le comportement live existant.

### Évaluation proposée des candidats

L'évaluateur du lab repose sur le Backtest Engine avec fenêtres multiples, validation out-of-sample et score de robustesse. Les métriques minimales à calculer et stocker sont :

- **return** (`total_return_pct`),
- **max drawdown** (`max_drawdown_pct`),
- **profit factor**,
- **stabilité OOS** : dispersion des scores entre fenêtres IS/OOS et pénalisation des candidats instables,
- **pénalité de complexité** : plus un prompt, template ou code devient complexe/fragile, plus son score diminue.

Le score de sélection doit être multi-objectif, pas un simple tri par rendement :

- rendement ajusté du risque,
- drawdown maîtrisé,
- stabilité inter-fenêtres,
- robustesse OOS,
- complexité contenue.

### Invariants imposés

- **Aucun impact sur le risk engine** : le lab ne lit éventuellement que ses contraintes comme référence, mais ne modifie ni logique ni seuils du moteur déterministe.
- **Isolation du live trading** : aucun candidat ne peut être auto-promu, aucun job d'évolution n'appelle MetaAPI pour exécuter des ordres, aucun résultat d'évolution n'entre automatiquement dans `Strategy Monitor` ou `ExecutionService`.
- **Promotion manuelle obligatoire** : un humain valide explicitement tout candidat avant intégration aux prompts actifs, stratégies `PAPER` ou stratégies `LIVE`.

## Conséquences

### Positives

- Amélioration attendue de la qualité et de la diversité des stratégies explorées.
- Meilleur usage du benchmark et du backtest existants comme évaluateurs structurés.
- Réduction du risque architectural par découplage fort entre exploration et exploitation.
- Cadre compatible avec une adoption progressive : prompts d'abord, stratégies ensuite, code sandboxé plus tard.
- Traçabilité renforcée des expérimentations et des raisons de promotion/rejet.

### Négatives

- Nouveau sous-système à opérer : orchestration, files, stockage d'artefacts, quotas compute.
- Coût de calcul potentiellement élevé selon la taille des populations et des fenêtres de backtest.
- Risque d'overfitting si la discipline d'évaluation OOS est insuffisante.
- Besoin d'un contrat clair entre candidats du lab et objets déjà gérés par Kairos Mesh (prompts, templates, stratégies validées).

### Trade-offs assumés

- On accepte une boucle d'apprentissage plus lente qu'une intégration live pour gagner en sûreté.
- On accepte un coût d'infrastructure supplémentaire pour préserver les frontières critiques.
- On retarde l'évolution de code de stratégie à une phase ultérieure afin de limiter le rayon d'impact initial.

## Plan d'implémentation progressif
- **Phase 1 : Foundations — Prompt Evolution Offline**
  - Périmètre : faire évoluer offline les prompts de `strategy-designer`, `trader-agent`, `bullish-researcher`, `bearish-researcher`.
  - Livrables : job/service séparé OpenEvolve, versionning des candidats, connecteur d'évaluation vers backtests multi-fenêtres, stockage des scores et artefacts.
  - Garde-fous : aucune écriture automatique dans les prompts actifs ; revue humaine obligatoire.
  - Effort estimé : **5 à 7 jours**.

- **Phase 2 : Strategy Template / Parameter Evolution**
  - Périmètre : faire évoluer templates sélectionnés, paramètres bornés et variantes de configuration.
  - Livrables : représentation canonique des candidats, score multi-objectif, leaderboard offline, workflow de promotion vers stratégie validable.
  - Garde-fous : bornes strictes de paramètres, evaluation OOS obligatoire, promotion manuelle vers `DRAFT` ou `VALIDATED` seulement après revue.
  - Effort estimé : **7 à 10 jours**.

- **Phase 3 : Sandbox Code Evolution (optionnel, ultérieur)**
  - Périmètre : autoriser l'évolution de code de stratégie dans un environnement sandboxé, sans accès au chemin live.
  - Livrables : sandbox d'exécution, contrôles statiques, politiques de sécurité, corpus de tests/backtests obligatoires avant revue.
  - Garde-fous : aucun chargement direct en production ; revue humaine et validation étendue obligatoires.
  - Effort estimé : **10 à 15 jours**.

## Risques et mitigations

- **Risque : overfitting sur l'historique**
  - Mitigation : multi-fenêtres, séparation IS/OOS, pénalisation de variance, seuil minimal de robustesse avant promotion.

- **Risque : explosion du coût de calcul**
  - Mitigation : quotas par campagne, populations bornées, arrêt anticipé, priorisation des niches prometteuses.

- **Risque : dérive qualitative des prompts**
  - Mitigation : règles de scoring explicites, benchmark de régression, comparaison au baseline, revue humaine avant activation.

- **Risque : couplage implicite avec le pipeline live**
  - Mitigation : service séparé, stockage séparé, API de promotion explicite, aucune écriture automatique dans les stratégies actives.

- **Risque : contamination des frontières critiques**
  - Mitigation : exclusion explicite du moteur de risque et de l'exécution broker du périmètre d'évolution ; contrôles d'architecture à la review.

- **Risque : dette de gouvernance sur les candidats générés**
  - Mitigation : versionning complet, métadonnées de provenance, conservation des scores, historique de décisions de promotion/rejet.

## Liens

- Architecture : `docs/architecture.md`
- Pipeline de décision : `docs/decision-pipeline.md`
- Gouvernance et risque : `docs/risk-and-governance.md`
- Implémentation existante du benchmark : `backend/app/services/benchmark/engine.py`
- Implémentation existante du strategy designer : `backend/app/services/strategy/designer.py`
- Gestion des stratégies et promotion : `backend/app/api/routes/strategies.py`
- OpenEvolve : `https://github.com/algorithmicsuperintelligence/openevolve`
