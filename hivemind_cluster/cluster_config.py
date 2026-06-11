#!/usr/bin/env python3
"""
HiveMind Cluster Configuration Parser
======================================

Parse et valide clusters.yaml — la source canonique de la config Phase 2.

Usage:
    from hivemind_cluster.cluster_config import ClusterConfig
    cfg = ClusterConfig("clusters.yaml")
    cfg.get_cluster_for_agent("alice")    # → "audit"
    cfg.get_weight("audit")               # → 1.0
    cfg.get_members("fiscal")             # → ["david", "eve"]
    cfg.all_agents()                      # → {"alice", "bob", ..., "frank"}
    cfg.validate()                        # → liste d'erreurs (vide = OK)
    cfg.to_cluster_weights_json()         # → dict pour cluster_weights.json
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


# ── Default path resolution ─────────────────────────────────────────

def _find_clusters_yaml(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Trouve clusters.yaml : explicite > cwd > repo root > profile global."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p

    candidates = [
        Path("clusters.yaml"),
        Path("../clusters.yaml"),
        Path(__file__).resolve().parent.parent / "clusters.yaml",  # repo root
    ]
    # Chercher dans le profil Hermes actif si défini
    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    hermes_profile = os.environ.get("HERMES_PROFILE", "default")
    profile_clusters = Path(hermes_home) / "profiles" / hermes_profile / "clusters.yaml"
    if profile_clusters.exists():
        candidates.append(profile_clusters)

    for c in candidates:
        if c.exists():
            return c
    return None


# ── ClusterConfig class ──────────────────────────────────────────────

class ClusterConfig:
    """
    Configuration des clusters du HiveMind Phase 2.

    Chargée depuis clusters.yaml. Offre lookup, validation,
    et génération du cluster_weights.json pour backward compat.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = _find_clusters_yaml(path)
        self._data = {}
        self._agent_to_cluster: dict[str, str] = {}
        self._loaded = False

        if self.path:
            self._load()

    def _load(self):
        """Charge clusters.yaml (YAML ou JSON)."""
        if not self.path or not self.path.exists():
            return

        content = self.path.read_text(encoding="utf-8")

        # Essayer YAML d'abord, fallback JSON
        if yaml is not None:
            try:
                self._data = yaml.safe_load(content) or {}
                self._loaded = True
            except yaml.YAMLError:
                pass

        if not self._loaded:
            import json
            try:
                self._data = json.loads(content)
                self._loaded = True
            except json.JSONDecodeError:
                print(f"[WARN] {self.path}: format non reconnu (ni YAML ni JSON)")
                return

        # Construire l'index agent → cluster
        self._build_agent_index()

    def _build_agent_index(self):
        """Construit le mapping agent → cluster_name."""
        self._agent_to_cluster = {}
        clusters = self._data.get("clusters", {})
        for cluster_name, cfg in clusters.items():
            if not isinstance(cfg, dict):
                continue
            for member in cfg.get("members", []):
                if member in self._agent_to_cluster:
                    print(f"[WARN] Agent '{member}' présent dans deux clusters: "
                          f"{self._agent_to_cluster[member]} et {cluster_name}")
                self._agent_to_cluster[member] = cluster_name

    # ── Lookup ──────────────────────────────────────────────────

    @property
    def clusters(self) -> dict:
        """Retourne {cluster_name: config}."""
        return self._data.get("clusters", {})

    def get_cluster_for_agent(self, agent: str) -> Optional[str]:
        """Retourne le nom du cluster auquel appartient un agent, ou None."""
        return self._agent_to_cluster.get(agent)

    def get_weight(self, cluster_name: str) -> float:
        """Poids de base d'un cluster (défaut 1.0)."""
        c = self.clusters.get(cluster_name, {})
        return c.get("weight", 1.0)

    def get_expertise(self, cluster_name: str) -> list[str]:
        """Domaines d'expertise d'un cluster."""
        c = self.clusters.get(cluster_name, {})
        return c.get("expertise", [])

    def get_members(self, cluster_name: str) -> list[str]:
        """Membres d'un cluster."""
        c = self.clusters.get(cluster_name, {})
        return c.get("members", [])

    def get_profile(self, cluster_name: str) -> Optional[str]:
        """Profil Hermes associé à un cluster."""
        c = self.clusters.get(cluster_name, {})
        return c.get("profile")

    def all_agents(self) -> set[str]:
        """Tous les agents connus (tous clusters confondus)."""
        return set(self._agent_to_cluster.keys())

    def is_known_agent(self, agent: str) -> bool:
        """True si l'agent est listé dans un cluster."""
        return agent in self._agent_to_cluster

    @property
    def expertise_multiplier(self) -> float:
        return self._data.get("expertise_multiplier", 2.0)

    @property
    def monopoly_multiplier(self) -> float:
        return self._data.get("monopoly_multiplier", 3.0)

    # ── Validation ──────────────────────────────────────────────

    def validate(self) -> list[str]:
        """
        Valide la configuration. Retourne une liste d'erreurs (vide = OK).

        Vérifications :
        - Chaque cluster a au moins un membre
        - Pas de membre en double entre clusters
        - Pas de chevauchement d'expertise (warning, pas bloquant)
        - Les poids sont > 0
        """
        errors = []
        clusters = self.clusters

        if not clusters:
            errors.append("Aucun cluster défini")
            return errors

        seen_members = {}
        all_expertise = {}  # expertise_term → cluster_name

        for name, cfg in clusters.items():
            if not isinstance(cfg, dict):
                errors.append(f"Cluster '{name}': config invalide (attendu dict)")
                continue

            # Poids > 0
            weight = cfg.get("weight", 1.0)
            if weight <= 0:
                errors.append(f"Cluster '{name}': weight doit être > 0 (actuel: {weight})")

            # Au moins un membre
            members = cfg.get("members", [])
            if not members:
                errors.append(f"Cluster '{name}': aucun membre défini")

            # Profil associé
            if not cfg.get("profile"):
                errors.append(f"Cluster '{name}': 'profile' non défini")

            # Doublons de membres
            for m in members:
                if m in seen_members:
                    errors.append(
                        f"Agent '{m}' dans deux clusters: "
                        f"'{seen_members[m]}' et '{name}'"
                    )
                seen_members[m] = name

            # Chevauchement d'expertise (warning)
            for term in cfg.get("expertise", []):
                term_lower = term.lower()
                if term_lower in all_expertise:
                    errors.append(
                        f"[WARN] Expertise '{term}' partagée entre "
                        f"'{all_expertise[term_lower]}' et '{name}' "
                        f"— aucun n'aura le bonus monopole pour ce terme"
                    )
                all_expertise[term_lower] = name

        return errors

    # ── Export ──────────────────────────────────────────────────

    def to_cluster_weights_json(self) -> dict:
        """
        Génère le dict équivalent à cluster_weights.json
        pour backward compat avec merge_engine_weighted.py.
        """
        return {
            "_about": "Généré depuis clusters.yaml — ne pas éditer.",
            "_source": str(self.path) if self.path else "unknown",
            "expertise_multiplier": self.expertise_multiplier,
            "monopoly_multiplier": self.monopoly_multiplier,
            "clusters": {
                name: {
                    "weight": cfg.get("weight", 1.0),
                    "expertise": cfg.get("expertise", []),
                }
                for name, cfg in self.clusters.items()
            },
        }

    def write_cluster_weights_json(self, output_path: str) -> str:
        """Écrit cluster_weights.json à partir de clusters.yaml."""
        import json
        data = self.to_cluster_weights_json()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path

    # ── Display ─────────────────────────────────────────────────

    def summary(self) -> str:
        """Résumé lisible de la configuration."""
        lines = []
        lines.append(f"📋 Cluster Config: {self.path or 'N/A'}")
        lines.append(f"   Multiplicateurs: expertise ×{self.expertise_multiplier}, "
                     f"monopole ×{self.monopoly_multiplier}")
        lines.append("")
        for name, cfg in sorted(self.clusters.items()):
            if not isinstance(cfg, dict):
                continue
            w = cfg.get("weight", "?")
            profile = cfg.get("profile", "?")
            members = cfg.get("members", [])
            expertise = cfg.get("expertise", [])
            lines.append(f"   🏷️  {name} (weight={w}, profile={profile})")
            lines.append(f"      Expertise: {', '.join(expertise[:8])}"
                        f"{'...' if len(expertise) > 8 else ''}")
            lines.append(f"      Membres: {', '.join(members)}")
            lines.append("")
        return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="HiveMind Cluster Config — parse et valide clusters.yaml"
    )
    parser.add_argument(
        "--config", "-c",
        help="Chemin vers clusters.yaml (auto-détecté si absent)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Valide la configuration",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Affiche un résumé",
    )
    parser.add_argument(
        "--export-weights", metavar="PATH",
        help="Exporte cluster_weights.json vers PATH",
    )
    parser.add_argument(
        "--agent", metavar="NAME",
        help="Affiche le cluster d'un agent",
    )

    args = parser.parse_args()

    cfg = ClusterConfig(args.config)

    if not cfg._loaded:
        print("❌ Aucune configuration trouvée.")
        print("   Cherché dans : cwd, repo root, ~/.hermes/profiles/<actif>/")
        sys.exit(1)

    if args.validate:
        errors = cfg.validate()
        if errors:
            print(f"❌ {len(errors)} erreur(s) :")
            for e in errors:
                print(f"   • {e}")
            sys.exit(1)
        else:
            print("✅ Configuration valide")

    if args.summary:
        print(cfg.summary())

    if args.agent:
        cluster = cfg.get_cluster_for_agent(args.agent)
        if cluster:
            print(f"✅ {args.agent} → cluster '{cluster}' "
                  f"(weight={cfg.get_weight(cluster)}, "
                  f"members={cfg.get_members(cluster)})")
        else:
            print(f"❌ Agent '{args.agent}' inconnu")
            print(f"   Agents connus : {sorted(cfg.all_agents())}")

    if args.export_weights:
        cfg.write_cluster_weights_json(args.export_weights)
        print(f"✅ cluster_weights.json exporté → {args.export_weights}")

    if not any([args.validate, args.summary, args.agent, args.export_weights]):
        # Mode par défaut : summary + validate
        print(cfg.summary())
        errors = cfg.validate()
        if errors:
            print(f"⚠️  {len(errors)} remarque(s) :")
            for e in errors:
                print(f"   • {e}")


if __name__ == "__main__":
    main()
