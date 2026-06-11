# HiveMind Cluster — Guide de configuration

> Tout ce qu'il faut savoir sur le paramétrage des poids, clusters, expertises, et `.env`.

---

## clusters.yaml — le fichier maître

C'est **LA source unique de vérité** pour toute la Phase 2. Un seul fichier, versionné dans Git, partagé par tous les membres du Global.

Emplacement : `~/.hermes/profiles/<global>/clusters.yaml`

### Structure complète

```yaml
# ── Multiplicateurs globaux ──
expertise_multiplier: 2.0    # ×2 quand le contenu match l'expertise du cluster
monopoly_multiplier: 3.0     # ×3 quand AUCUN autre cluster n'a cette expertise

# ── Définition des clusters ──
clusters:
  audit:
    profile: cabinet-audit        # Nom du profil Hermes
    weight: 1.0                   # Poids de base (> 0)
    expertise:                     # Mots-clés d'expertise (sous-chaîne, insensible casse)
      - audit
      - IFRS
      - ISA
      - fraude
      - circularisation
      - matérialité
    members:                       # Agents autorisés dans ce cluster
      - alice
      - bob
      - charles

  fiscal:
    profile: cabinet-fiscal
    weight: 1.5
    expertise:
      - fiscalité
      - TVA
      - prix de transfert
      - imposition
    members:
      - david
      - eve
```

### Validation

```bash
python3 -m hivemind_cluster.cluster_config \
  --config clusters.yaml --validate
```

Vérifie :
- Chaque cluster a au moins un membre
- Pas de membre en double entre clusters
- Poids > 0
- Profil défini pour chaque cluster
- Expertise partagée entre clusters → avertissement (monopole cassé)

---

## Comment fonctionne la pondération ?

### Formule

```
importance_finale = min(importance × weight × bonus, 1.0)

bonus démarre à 1.0 :
  SI le contenu contient un mot-clé d'expertise du cluster → bonus × 2.0
  SI ce mot-clé est UNIQUE à ce cluster (monopole)            → bonus × 3.0
```

### Exemple concret

```yaml
# clusters.yaml
clusters:
  fiscal:
    weight: 1.5
    expertise: [fiscalité, TVA, prix de transfert]
  audit:
    weight: 1.0
    expertise: [audit, IFRS, fraude]
```

Mémoire : **"TVA intracommunautaire : nouveau seuil à 10 000€"**
- Cluster : fiscal
- Poids de base : ×1.5
- Match "TVA" → expertise ×2.0
- "TVA" n'est que dans fiscal → monopole ×3.0
- **Total : ×9.0** (importance 0.85 × 9 = 7.65 → cap à 1.0)

Mémoire : **"Note générale sur le crédit d'impôt recherche"**
- Cluster : fiscal
- Poids de base : ×1.5
- Aucun mot-clé d'expertise matché → pas de bonus
- **Total : ×1.5** (importance 0.6 × 1.5 = 0.9)

### Plafond

L'importance est **cappée à 1.0**. Une mémoire ne peut pas dépasser 1.0, même avec un poids très élevé.

---

## Comment choisir les poids ?

| Règle | Explication |
|---|---|
| **Poids = crédibilité relative** | Un cluster avec plus d'expérience ou de spécialisation a un poids plus élevé |
| **Défaut : 1.0** | Tous les clusters partent à égalité |
| **Plage : 0.5 – 3.0** | En dessous de 0.5 = cluster quasi ignoré. Au-dessus de 3.0 = écrase tout |
| **Exemple réel** | Audit (1.0), Fiscal (1.5 — plus technique), Juridique (2.0 — avis qui tranche) |

---

## Comment choisir les expertises ?

### Règles

1. **Mots suffisamment longs et distinctifs**
   - ✅ `fiscalité`, `circularisation`, `contentieux`
   - ❌ `fisc` (trop court, faux positifs), `taxe` (matche `syntaxe`)

2. **Pas de chevauchement entre clusters**
   - Si deux clusters ont le même mot-clé → aucun n'a le bonus monopole
   - Vérifier : `python3 -m hivemind_cluster.cluster_config --validate`

3. **Spécifiques au domaine**
   - Un mot-clé est matché si présent n'importe où dans le contenu
   - `droit` matchera `endroit` → préférer `droit des sociétés` (si possible) ou `contentieux`

4. **5-10 expertises par cluster**
   - Trop peu : beaucoup de mémoires ne matchent rien → poids de base uniquement
   - Trop : risque de faux positifs

### Anti-patterns

| ❌ Mauvais choix | Problème | ✅ Meilleur choix |
|---|---|---|
| `droit` | Matche `endroit`, `adroit` | `contentieux`, `droit-sociétés` |
| `taxe` | Matche `syntaxe`, `taxer` | `imposition`, `CGI` |
| `note` | Beaucoup trop commun | `note-interne`, `procédure` |
| `client` | Présent partout | `client-sensible`, `KYC` |

---

## .env — Règles de sécurité

```
✅ Chaque membre a SON .env avec SES clés API
✅ .env est dans .gitignore → jamais dans Git
✅ .env est HORS du dossier Syncthing → jamais sync
✅ Chaque machine a son .env

❌ JAMAIS partager .env
❌ JAMAIS commiter .env
❌ JAMAIS mettre .env dans memory/ (dossier Syncthing)
❌ JAMAIS copier-coller les clés des autres
```

### Emplacement

```
~/.hermes/profiles/
├── cabinet/           ← Profil Global
│   ├── .env           ← LOCAL (clés du membre qui gère le Global)
│   └── memory/        ← Syncthing (pas .env ici !)
│
├── cabinet-audit/     ← Cluster Audit
│   ├── .env           ← LOCAL (clés d'Alice, Bob, Charles — chaqu'un le sien)
│   └── memory/        ← Syncthing
│
└── cabinet-fiscal/
    ├── .env           ← LOCAL (clés de David, Eve)
    └── memory/
```

### Template .env.example

```bash
# Clés API — JAMAIS COMMIT, JAMAIS SYNCTHING
# Copier en .env et remplir avec VOS clés

DEEPSEEK_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

---

## Ajouter un nouveau cluster

1. **Éditer `clusters.yaml`** dans le profil Global :

```yaml
clusters:
  # ... existants ...
  conseil:
    profile: cabinet-conseil
    weight: 1.2
    expertise: [stratégie, due-diligence, évaluation, fusion]
    members: [grace, henry]
```

2. **Valider :**
```bash
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --validate
```

3. **Créer le profil :**
```bash
python3 -m hivemind.hivemind_cli init cabinet-conseil
```

4. **Configurer Syncthing** pour le nouveau cluster (events, export, inbox).

5. **Commit + push** `clusters.yaml` dans Git pour que tous les membres du Global le reçoivent.

---

## Ajouter/retirer un membre

Éditer `clusters.yaml` :

```yaml
clusters:
  audit:
    members: [alice, bob, charles, diana]  # ← ajouter diana
```

Puis commit + push. La validation détectera automatiquement si `diana` est déjà dans un autre cluster.

**Pas besoin de recréer le profil** — le merge engine lit `clusters.yaml` au moment du merge. Le nouvel agent est reconnu immédiatement.

---

## Changer les multiplicateurs globaux

```yaml
expertise_multiplier: 2.5    # Plus sensible aux expertises
monopoly_multiplier: 2.0     # Moins de bonus monopole
```

Impact immédiat au prochain merge pondéré. Pas besoin de redémarrer.

---

## cluster_weights.json

Ce fichier est **généré automatiquement** depuis `clusters.yaml`. Ne pas l'éditer.

```bash
# Générer depuis clusters.yaml
python3 -m hivemind_cluster.cluster_config \
  --config clusters.yaml \
  --export-weights cluster_weights.json
```

Il est utilisé comme fallback par le merge engine si `clusters.yaml` n'est pas trouvé.

---

## Résumé des commandes de gestion

```bash
# Lister tous les clusters
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --summary

# Valider la configuration
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --validate

# Voir le cluster d'un agent
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --agent alice

# Générer cluster_weights.json
python3 -m hivemind_cluster.cluster_config --config clusters.yaml --export-weights cluster_weights.json

# Via la CLI hivemind
python3 -m hivemind.hivemind_cli cluster list
python3 -m hivemind.hivemind_cli cluster show audit
python3 -m hivemind.hivemind_cli cluster validate
```
