# HiveMind Cluster — Guide de déploiement

> Déploiement complet Phase 2 : du git clone au multi-cluster opérationnel.

## Prérequis

- **hivemind** (Phase 1) installé : `pip install git+https://github.com/rtsitola/hivemind.git`
- **Syncthing** installé sur chaque machine membre
- **Git** configuré avec accès GitHub
- **Hermes Agent** installé (optionnel mais recommandé)

---

## Architecture cible

```
~/.hermes/profiles/
│
├── cabinet/                          ← Profil GLOBAL (lit tous les clusters)
│   ├── skills/          ← Git
│   ├── config.yaml      ← Git (modèle, provider, outils communs)
│   ├── USER.md          ← Git (personnalité collective)
│   ├── clusters.yaml    ← Git ★ (définition des clusters, poids, membres)
│   ├── .env             ← LOCAL — JAMAIS sync (clés API personnelles)
│   └── memory/
│       ├── events/       ← Syncthing (reçoit les exports des clusters)
│       │   ├── audit.jsonl
│       │   ├── fiscal.jsonl
│       │   └── juridique.jsonl
│       └── consolidated.db ← LOCAL — reconstruit par merge pondéré
│
├── cabinet-audit/                   ← Cluster Audit
│   ├── skills/          ← Git
│   ├── .env             ← LOCAL
│   └── memory/
│       ├── events/       ← Syncthing (écritures des membres)
│       │   ├── alice.jsonl
│       │   ├── bob.jsonl
│       │   └── charles.jsonl
│       ├── export/       ← Syncthing (→ global/events/)
│       │   └── audit.jsonl
│       ├── inbox/        ← Syncthing (reçoit d'autres clusters)
│       │   ├── from-fiscal.jsonl
│       │   └── from-juridique.jsonl
│       └── consolidated.db ← LOCAL
│
├── cabinet-fiscal/                   ← Cluster Fiscal
│   └── ... (même structure)
│
└── cabinet-juridique/                ← Cluster Juridique
    └── ... (même structure)
```

---

## Étape 1 : Créer le profil Global

```bash
# Cloner hivemind-cluster
git clone https://github.com/rtsitola/hivemind-cluster.git /tmp/hivemind-cluster
export PYTHONPATH=/tmp/hivemind-cluster:$(pip show hivemind 2>/dev/null | grep Location | cut -d' ' -f2)

# Créer le profil Global (le "cabinet")
python3 -m hivemind.hivemind_cli init cabinet
```

Ceci crée `~/.hermes/profiles/cabinet/` avec la structure Phase 1 standard.

---

## Étape 2 : Configurer clusters.yaml

Copier `clusters.yaml` dans le profil Global et l'éditer :

```bash
cp /tmp/hivemind-cluster/clusters.yaml ~/.hermes/profiles/cabinet/
nano ~/.hermes/profiles/cabinet/clusters.yaml
```

**Exemple pour un cabinet d'audit :**

```yaml
expertise_multiplier: 2.0
monopoly_multiplier: 3.0

clusters:
  audit:
    profile: cabinet-audit
    weight: 1.0
    expertise: [audit, IFRS, ISA, fraude, circularisation, matérialité]
    members: [alice, bob, charles]

  fiscal:
    profile: cabinet-fiscal
    weight: 1.5
    expertise: [fiscalité, TVA, prix de transfert, imposition]
    members: [david, eve]

  juridique:
    profile: cabinet-juridique
    weight: 2.0
    expertise: [droit, contrat, contentieux, recours, sociétés]
    members: [frank]
```

**Valider :**
```bash
python3 -m hivemind_cluster.cluster_config --config ~/.hermes/profiles/cabinet/clusters.yaml --validate
```

> 📖 **Guide complet du paramétrage** → [CONFIG.md](CONFIG.md)

---

## Étape 3 : Configurer le .env du Global

```bash
cp ~/.hermes/profiles/cabinet/.env.example ~/.hermes/profiles/cabinet/.env
nano ~/.hermes/profiles/cabinet/.env
```

Remplir avec vos clés API :

```bash
DEEPSEEK_API_KEY=sk-xxxx
# OPENAI_API_KEY=sk-...    (optionnel)
# ANTHROPIC_API_KEY=sk-...  (optionnel)
```

> ⚠️ **.env = LOCAL, jamais sync.** Chaque membre a SON .env avec SES clés. Le fichier est dans `.gitignore` et hors de portée de Syncthing.

---

## Étape 4 : Créer les profils de cluster

Pour **chaque cluster** défini dans `clusters.yaml` :

```bash
python3 -m hivemind.hivemind_cli init cabinet-audit
python3 -m hivemind.hivemind_cli init cabinet-fiscal
python3 -m hivemind.hivemind_cli init cabinet-juridique
```

Puis configurer chaque `.env` et `USER.md`.

---

## Étape 5 : Configurer Syncthing

### 5.1 Partager la mémoire du cluster

Pour **chaque cluster** (ex: cabinet-audit), dans Syncthing (http://localhost:8384) :

1. **Add Folder** :
   - Folder ID : `hivemind-cabinet-audit-memory`
   - Folder Path : `~/.hermes/profiles/cabinet-audit/memory`

2. Partager avec les **Device ID** de tous les membres du cluster.

3. Sur les machines des membres : accepter le partage, corriger le Path.

### 5.2 Partager les exports vers le Global

Dans chaque cluster :

1. **Add Folder** :
   - Folder ID : `hivemind-cabinet-audit-export`
   - Folder Path : `~/.hermes/profiles/cabinet-audit/memory/export`

2. Partager uniquement avec la machine qui héberge le Global.

Sur la machine Global :
- Accepter le partage `hivemind-cabinet-audit-export`
- Path : `~/.hermes/profiles/cabinet/memory/events` (les exports arrivent directement dans events/)

> ⚠️ **Ne jamais partager `consolidated.db`** — il est reconstruit localement. Seuls les `.jsonl` voyagent.

### 5.3 Partager les inbox inter-cluster

Pour la communication directe entre clusters :

1. Dans chaque cluster, **Add Folder** :
   - Folder ID : `hivemind-cabinet-audit-inbox`
   - Folder Path : `~/.hermes/profiles/cabinet-audit/memory/inbox`

2. Partager avec les autres clusters (pas le Global).

---

## Étape 6 : Démarrer les watchers

Sur **chaque profil** (Global + chaque cluster), lancer le watcher :

```bash
# Watcher du Global
python3 -m hivemind.hivemind_cli serve cabinet &

# Watcher du cluster Audit
python3 -m hivemind.hivemind_cli serve cabinet-audit &

# etc.
```

Le watcher surveille `memory/events/`, déclenche le merge automatiquement, et pour le Global applique la pondération.

---

## Étape 7 : Vérifier

```bash
# Status de tous les profils
python3 -m hivemind.hivemind_cli status

# Vérifier les clusters
python3 -m hivemind_cluster.cluster_config \
  --config ~/.hermes/profiles/cabinet/clusters.yaml \
  --summary --validate

# Tester un export
python3 -m hivemind_cluster.export_engine \
  --db ~/.hermes/profiles/cabinet-audit/memory/consolidated.db \
  --export-dir /tmp/test-export --cluster audit --mode full --scope shared
```

---

## Flux quotidien

```
MATIN :
  1. Alice écrit une mémoire → alice.jsonl
  2. Syncthing sync → Bob et Charles reçoivent
  3. Watcher local merge → consolidated.db mis à jour

MIDI :
  4. Export Engine → audit.jsonl (scope=shared uniquement)
  5. Syncthing sync → Global reçoit audit.jsonl
  6. Watcher Global → merge pondéré → DB globale à jour

APRÈS-MIDI :
  7. Alice veut l'avis de Fiscal → inbox_writer → from-audit.jsonl
  8. Syncthing → David (Fiscal) reçoit → répond → inbox
  9. Global détecte une mémoire impactant tous → downstream → to-*.jsonl
```

---

## Dépannage

| Symptôme | Solution |
|---|---|
| Merge échoue | `python3 -m hivemind.merge_engine --events-dir <dir> --db <db>` (manuel) |
| Agent inconnu averti | Ajouter l'agent dans `clusters.yaml` → `members:` |
| Poids incorrect | Vérifier `clusters.yaml` → `python3 -m hivemind_cluster.cluster_config --validate` |
| Export vide | Vérifier `scope=shared` sur les mémoires à exporter |
| Syncthing out of sync | Vérifier que les dossiers sont partagés, devices connectés |
| consolidated.db corrompu | `rm consolidated.db && relancer le merge` |
| Conflit Git sur clusters.yaml | Résoudre manuellement (merge standard) |

---

## Prochaine étape

- [Guide de configuration des poids](CONFIG.md)
- [ONBOARDING.md](../hivemind/docs/ONBOARDING.md) — pour les nouveaux membres
- [SPEC-PHASE-2.md](../hivemind/docs/SPEC.md) — architecture détaillée
