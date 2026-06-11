#!/usr/bin/env python3
"""
Test de l'Export Engine + Global Merge
=======================================

Scénario complet Phase 2 :
  1. Créer 2 clusters simulés (audit, fiscal)
  2. Chaque cluster a ses propres mémoires (consolidated.db)
  3. Export engine : cluster → export/<cluster>.jsonl
  4. Global merge : lit les 2 exports → consolidated.db global
  5. Vérifier que le global voit tout
  6. Incrémental : nouvelle mémoire → export → global mis à jour
"""

import os
import sys
import json
import shutil
import sqlite3
import subprocess

# Import from hivemind package
from hivemind.merge_engine import merge as merge_engine_fn
from hivemind.hivemind_mnemosyne import HiveMindMemory

# Chemins
CLUSTER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_ENGINE = os.path.join(CLUSTER_DIR, "export_engine.py")
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "test_clusters")
AUDIT_EVENTS = os.path.join(TEST_DIR, "audit", "memory", "events")
AUDIT_DB = os.path.join(TEST_DIR, "audit", "memory", "consolidated.db")
FISCAL_EVENTS = os.path.join(TEST_DIR, "fiscal", "memory", "events")
FISCAL_DB = os.path.join(TEST_DIR, "fiscal", "memory", "consolidated.db")
EXPORT_DIR = os.path.join(TEST_DIR, "exports")
GLOBAL_EVENTS = os.path.join(TEST_DIR, "global", "memory", "events")
GLOBAL_DB = os.path.join(TEST_DIR, "global", "memory", "consolidated.db")


def cleanup():
    for d in [TEST_DIR]:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                for d2 in dirs:
                    os.rmdir(os.path.join(root, d2))
            os.rmdir(d)
    print("🧹 Nettoyage\n")


def run_export(db, cluster, mode="full"):
    """Run export engine subprocess."""
    result = subprocess.run(
        [sys.executable, EXPORT_ENGINE,
         "--db", db, "--export-dir", EXPORT_DIR,
         "--cluster", cluster, "--mode", mode, "--scope", "shared"],
        capture_output=True, text=True,
    )
    print(result.stdout.rstrip())
    if result.returncode != 0:
        print(f"[STDERR] {result.stderr}", file=sys.stderr)
    return result


def test_export_engine():
    cleanup()

    print("=" * 60)
    print("  TEST EXPORT ENGINE + GLOBAL MERGE")
    print("=" * 60)

    # ── Phase 1 : Créer les clusters ─────────────────────────────

    print("\n─── Phase 1 : Création des clusters Audit et Fiscal ───\n")

    os.makedirs(AUDIT_EVENTS, exist_ok=True)
    os.makedirs(FISCAL_EVENTS, exist_ok=True)

    audit = HiveMindMemory(events_dir=AUDIT_EVENTS, consolidated_db=AUDIT_DB, agent="alice")
    audit.remember("Client Omega : risque fraude élevé — circularisation obligatoire",
                   importance=0.95, scope="shared", source="audit")
    audit.remember("Seuil matérialité : 5% du résultat net",
                   importance=0.9, scope="shared", source="audit")
    audit.remember("Note interne : Alice suspecte un faux bilan chez Omega",
                   importance=0.8, scope="private", source="audit")
    audit.merge()

    fiscal = HiveMindMemory(events_dir=FISCAL_EVENTS, consolidated_db=FISCAL_DB, agent="david")
    fiscal.remember("Client Gamma : prix de transfert à documenter avant le 30/06",
                    importance=0.9, scope="shared", source="fiscal")
    fiscal.remember("TVA intracommunautaire : nouveau seuil à 10 000€ depuis janvier",
                    importance=0.85, scope="shared", source="fiscal")
    fiscal.remember("Note interne : David pense que Gamma minimise ses bénéfices",
                    importance=0.75, scope="private", source="fiscal")
    fiscal.merge()

    print(f"   Audit  : {audit.stats()['total']} mémoires (dont 1 private)")
    print(f"   Fiscal : {fiscal.stats()['total']} mémoires (dont 1 private)")

    # ── Phase 2 : Export engine ──────────────────────────────────

    print("\n─── Phase 2 : Export des clusters (scope=shared uniquement) ───\n")

    result = run_export(AUDIT_DB, "audit", "full")
    assert result.returncode == 0, f"Export audit failed: {result.stderr}"

    result = run_export(FISCAL_DB, "fiscal", "full")
    assert result.returncode == 0, f"Export fiscal failed: {result.stderr}"

    audit_export = os.path.join(EXPORT_DIR, "audit.jsonl")
    fiscal_export = os.path.join(EXPORT_DIR, "fiscal.jsonl")
    assert os.path.exists(audit_export), "audit.jsonl manquant"
    assert os.path.exists(fiscal_export), "fiscal.jsonl manquant"

    with open(audit_export) as f:
        audit_lines = f.readlines()
    assert len(audit_lines) == 2, f"Audit: attendu 2 shared, obtenu {len(audit_lines)}"
    for line in audit_lines:
        assert "private" not in json.loads(line)["payload"].get("scope", ""), "Mémoire private exportée !"
    print(f"   ✅ Audit : {len(audit_lines)} mémoires shared exportées, 0 private")

    with open(fiscal_export) as f:
        fiscal_lines = f.readlines()
    assert len(fiscal_lines) == 2, f"Fiscal: attendu 2 shared, obtenu {len(fiscal_lines)}"
    print(f"   ✅ Fiscal : {len(fiscal_lines)} mémoires shared exportées, 0 private")

    # ── Phase 3 : Global merge ───────────────────────────────────

    print("\n─── Phase 3 : Merge global (lit les 2 exports) ───\n")

    os.makedirs(GLOBAL_EVENTS, exist_ok=True)
    shutil.copy(audit_export, os.path.join(GLOBAL_EVENTS, "audit.jsonl"))
    shutil.copy(fiscal_export, os.path.join(GLOBAL_EVENTS, "fiscal.jsonl"))

    stats = merge_engine_fn(events_dir=GLOBAL_EVENTS, db_path=GLOBAL_DB)
    print(f"   Global : {stats['merged']} mémoires consolidées")

    conn = sqlite3.connect(GLOBAL_DB)
    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print(f"   Total global : {total} (attendu 4)")
    assert total == 4, f"Attendu 4, obtenu {total}"

    agents = [a[0] for a in conn.execute("SELECT DISTINCT agent FROM memories").fetchall()]
    print(f"   Agents : {agents}")
    assert "cluster:audit" in agents, "cluster:audit manquant"
    assert "cluster:fiscal" in agents, "cluster:fiscal manquant"
    conn.close()

    # ── Phase 4 : Incrémental ────────────────────────────────────

    print("\n─── Phase 4 : Incrémental — nouvelle mémoire audit ───\n")

    audit.remember("Client Omega : confirmer les provisions pour litiges avant le 15/07",
                   importance=0.88, scope="shared", source="audit")
    audit.merge()

    result = run_export(AUDIT_DB, "audit", "incremental")
    assert "Exportés   : 1" in result.stdout, f"Incremental: attendu 1 exporté, obtenu:\n{result.stdout}"

    shutil.copy(audit_export, os.path.join(GLOBAL_EVENTS, "audit.jsonl"))

    stats = merge_engine_fn(events_dir=GLOBAL_EVENTS, db_path=GLOBAL_DB)
    conn = sqlite3.connect(GLOBAL_DB)
    total2 = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    print(f"   Global après incrémental : {total2} (attendu 5)")
    assert total2 == 5, f"Attendu 5, obtenu {total2}"
    print(f"   ✅ Incrémental propagé au global")

    # ── Phase 5 : Recherche dans le global ──────────────────────

    print("\n─── Phase 5 : Recall dans le global ───\n")

    global_hm = HiveMindMemory(events_dir=GLOBAL_EVENTS, consolidated_db=GLOBAL_DB, agent="global")
    results = global_hm.recall("Client", limit=10)
    print(f"   Recherche 'Client' → {len(results)} résultats :")
    for r in results:
        print(f"     [{r['agent']}] {r['content'][:70]}...")
    assert len(results) >= 2, f"Attendu ≥ 2 résultats pour 'Client'"

    private_results = global_hm.recall("suspecte", limit=5)
    print(f"\n   Recherche 'suspecte' (private) → {len(private_results)} résultats")
    assert len(private_results) == 0, "Une mémoire private a fuité dans le global !"
    print(f"   ✅ Aucune mémoire private dans le global")

    print("\n" + "=" * 60)
    print("  ✅ EXPORT ENGINE + GLOBAL MERGE FONCTIONNELS")
    print("=" * 60)


if __name__ == "__main__":
    test_export_engine()
