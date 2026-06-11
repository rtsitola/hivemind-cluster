# HiveMind Cluster — Phase 2

<p align="center">
  <img width="800" alt="Yggdrasil — Three roots, one tree" src="hivemind_cluster/docs/yggdrasil.jpg" />
</p>

> **Yggdrasil, l'Arbre-Monde** — trois racines distinctes (Audit, Fiscal, Juridique) nourrissent un tronc unique (le Global). Les branches redistribuent la connaissance vers chaque cluster. En arrière-plan, Athéna et sa chouette veillent — la sagesse de la Phase 1 protège l'intelligence collective de la Phase 2.

Multi-cluster : N HiveMinds (Phase 1) nourrissent 1 Global.

> ⚠️ **Statut : Alpha — pas encore battle-tested.**
> Le code est complet et les tests unitaires passent (4/4), mais ce projet n'a **jamais été déployé en production** avec de vrais utilisateurs et Syncthing réel.

**En attente de :**
- [ ] Test Syncthing multi-writer (2 machines écrivent simultanément)
- [ ] Test Phase 2 intégré (3 clusters simulés → 1 global, flux complet)
- [ ] Hermes skill hivemind (utiliser `remember`/`recall` directement dans le chat)
- [ ] Déploiement réel avec 3 utilisateurs × 1 semaine
- [ ] Monitoring/alerte si merge échoue ou watcher down
- [ ] Stratégie de purge des `processed_events`

**Prêt pour le développement et les tests. Pas encore pour la production.**

**Dépendance :** `pip install hivemind` (Phase 1 package)

📖 **Documentation :**
- [Guide de déploiement](DEPLOYMENT.md) — étape par étape, Syncthing, watchers
- [Guide de configuration](CONFIG.md) — poids, expertises, .env, membres
- [Spécification Phase 2](PHASE.md) — architecture complète

## Structure

```
hivemind-cluster/
├── hivemind_cluster/
│   ├── export_engine.py           ← Cluster → Global (filtrage scope)
│   ├── merge_engine_weighted.py   ← Merge avec pondération par cluster
│   ├── inbox_writer.py            ← Communication directe inter-cluster
│   ├── redistribute.py            ← Global → Clusters (downstream)
│   ├── cluster_config.py          ← Parser + validator clusters.yaml
│   ├── cluster_weights.json       ← Config poids (généré, ne pas éditer)
│   └── tests/
│       ├── test_export.py         ← Test export engine
│       ├── test_weighted_merge.py ← Test merge pondéré
│       ├── test_inbox.py          ← Test inbox inter-cluster
│       └── test_redistribute.py   ← Test downstream
├── clusters.yaml                  ← Définition canonique (source unique)
└── PHASE.md                       ← Spécification complète
```

## Installation

```bash
# Cloner
git clone https://github.com/rtsitola/hivemind-cluster.git
cd hivemind-cluster

# Installer la dépendance Phase 1
pip install git+https://github.com/rtsitola/hivemind.git
# Ou en développement :
# git clone https://github.com/rtsitola/hivemind.git ../hivemind
# export PYTHONPATH=$(cd ../hivemind && pwd):$(pwd)
```

## Quick start

```bash
# Install dependencies
pip install hivemind
export PYTHONPATH=$(cd ../hivemind && pwd):$(pwd)

# Lister les clusters
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --summary

# Valider la config
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --validate

# Exporter un cluster vers le global
python3 -m hivemind_cluster.export_engine \
  --db ../cabinet-audit/memory/consolidated.db \
  --export-dir ./exports --cluster audit

# Merge global avec pondération
python3 -m hivemind_cluster.merge_engine_weighted \
  --events-dir ./global/events --db ./global/consolidated.db \
  --config clusters.yaml

# Envoyer un message inter-cluster
python3 -m hivemind_cluster.inbox_writer --cross-dir ./cross-cluster \
  --from audit --from-agent alice --to fiscal \
  "Ce montage est-il conforme ?"

# Redistribuer du global vers les clusters
python3 -m hivemind_cluster.redistribute \
  --db ./global/consolidated.db --downstream-dir ./downstream \
  --config clusters.yaml
```

## Tests

```bash
cd hivemind_cluster/tests
PYTHONPATH=$(cd ../../hivemind && pwd):$(cd ../.. && pwd) \
  python3 test_export.py && python3 test_weighted_merge.py && \
  python3 test_inbox.py && python3 test_redistribute.py
```

## Architecture

```
Cluster Audit ──export──┐
Cluster Fiscal ─export──┼──► Global (merge pondéré)
Cluster Juridique ──────┘         │
                                  ▼
                          downstream/ ──► chaque cluster

Inter-cluster : inbox_writer.py → cross-cluster/ → Syncthing → autres clusters
```
