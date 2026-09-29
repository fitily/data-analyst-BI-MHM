import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pymysql
from rapidfuzz import fuzz, process

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_CONFIG = {
    "host": os.getenv("MHM_DB_HOST", "localhost"),
    "port": int(os.getenv("MHM_DB_PORT", "3306")),
    "user": os.getenv("MHM_DB_USER", "lecture_ro"),
    "password": os.getenv("MHM_DB_PASSWORD", ""),
    "database": os.getenv("MHM_DB_NAME", "prod_mhm_ps"),
    "charset": "utf8mb4",
}

FILE_GAZETTEER = PROJECT_ROOT / "scripts" / "data.csv"
SEED_OUTPUT = PROJECT_ROOT / "seeds" / "seed_patients_adresses_cleaned.csv"

TABLE = "patients"
COL_ID = "id"
COL_ADRESSE = "adress"  # Changez en "adresse" si nécessaire
COL_FONKONTANY = "fonkontany"
COL_COMMUNE = "commune"
COL_DISTRICT = "district"

SEUIL_SCORE_FUZZY = 78
VALEUR_INCONNUE = "INCONNU"

MOTIF_BRUIT = [
    r"\bLOT\s*\S+\b",
    r"\bVO\s*\S+\b",
    r"\bBIS\b", r"\bTER\b",
    r"\bIMM(?:EUBLE)?\s*\S*\b",
    r"\bCITE\b", r"\bRUE\b", r"\bRTE\b", r"\bROUTE\b",
    r"\bPRES\s+DE?\b",
    r"\b\d+\b",
]

# ------------------------------------------------------------------
# 2. PRÉPARATION DES DONNÉES & INDEXATION
# ------------------------------------------------------------------

def normaliser_texte(texte):
    """Normalise un texte pour rendre les comparaisons insensibles aux accents."""
    if pd.isna(texte):
        return ""
    t = unicodedata.normalize("NFKD", str(texte))
    t = "".join(char for char in t if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", t.upper()).strip()


def nettoyer(texte):
    """Nettoie le texte libre de l'adresse (bruit, accents et caractères spéciaux)."""
    t = normaliser_texte(texte)
    for motif in MOTIF_BRUIT:
        t = re.sub(motif, " ", t)
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def charger_indexes(filepath=FILE_GAZETTEER):
    """Charge le référentiel et construit les index exacts et fuzzy."""
    try:
        df_ref = pd.read_csv(filepath, sep=";", encoding="utf-8", dtype=str)
    except UnicodeDecodeError:
        df_ref = pd.read_csv(filepath, sep=";", encoding="latin1", dtype=str)

    dict_communes = {}
    dict_fkt = {}

    # 1. Indexation des Communes
    df_communes = df_ref[['Kaomina', 'Distrika', 'Region']].drop_duplicates()
    for _, row in df_communes.iterrows():
        c_name = normaliser_texte(row["Kaomina"])
        if c_name and c_name not in dict_communes:
            dict_communes[c_name] = {
                "fonkontany": VALEUR_INCONNUE,
                "commune": c_name,
                "district": normaliser_texte(row["Distrika"]),
                "niveau": "COMMUNE"
            }

    # 2. Indexation des Fokontany
    df_fkt = df_ref[['fokontany', 'Kaomina', 'Distrika', 'Region']].drop_duplicates()
    for _, row in df_fkt.iterrows():
        f_name = normaliser_texte(row["fokontany"])
        if f_name and f_name not in dict_fkt:
            dict_fkt[f_name] = {
                "fonkontany": f_name,
                "commune": normaliser_texte(row["Kaomina"]),
                "district": normaliser_texte(row["Distrika"]),
                "niveau": "FOKONTANY"
            }

    return {
        "communes": dict_communes,
        "fokontany": dict_fkt,
        "commune_names": list(dict_communes),
        "fokontany_names": list(dict_fkt),
    }

# ------------------------------------------------------------------
# 3. ALGORITHME DE MATCHING HYBRIDE (EXACT + FUZZY)
# ------------------------------------------------------------------

def identifier_lieu(adresse, indexes):
    txt_clean = nettoyer(adresse)
    if not txt_clean:
        return None, 0.0, "VIDE"

    mots = [m for m in txt_clean.split() if len(m) >= 3]
    communes = indexes["communes"]
    fokontany = indexes["fokontany"]

    # Les noms multi-mots sont vérifiés en premier pour éviter un faux match
    # sur un mot générique contenu dans une adresse.
    for nom in sorted(communes, key=len, reverse=True):
        if nom in txt_clean:
            return communes[nom], 100.0, "EXACT_COMMUNE"
    for nom in sorted(fokontany, key=len, reverse=True):
        if nom in txt_clean:
            return fokontany[nom], 95.0, "EXACT_FOKONTANY"

    for mot in mots:
        if mot in communes:
            return communes[mot], 100.0, "EXACT_COMMUNE"
        if mot in fokontany:
            return fokontany[mot], 95.0, "EXACT_FOKONTANY"

    meilleur_item = None
    meilleur_score = 0.0
    meilleur_type = "NON_TROUVE"
    for mot in mots:
        for noms, index, type_match in (
            (indexes["commune_names"], communes, "FUZZY_COMMUNE"),
            (indexes["fokontany_names"], fokontany, "FUZZY_FOKONTANY"),
        ):
            resultat = process.extractOne(mot, noms, scorer=fuzz.ratio)
            if resultat is None:
                continue
            nom, score, _ = resultat
            score -= abs(len(mot) - len(nom)) * 3
            if score >= SEUIL_SCORE_FUZZY and score > meilleur_score:
                meilleur_item = index[nom]
                meilleur_score = score
                meilleur_type = type_match

    return meilleur_item, round(max(0.0, meilleur_score), 2), meilleur_type


def extraire_patients(conn):
    """Extrait tous les patients actifs ayant une adresse exploitable."""
    query = f"""
        SELECT `{COL_ID}` AS patient_id, `{COL_ADRESSE}` AS adresse_raw
        FROM `{TABLE}`
        WHERE COALESCE(deleted, 0) = 0
          AND `{COL_ADRESSE}` IS NOT NULL
          AND TRIM(`{COL_ADRESSE}`) != ''
    """
    return pd.read_sql(query, conn)


def construire_seed(df_patients, indexes):
    """Applique le matching et retourne un seed dbt déterministe et valide."""
    lignes = []
    for row in df_patients.itertuples(index=False):
        item, score, methode = identifier_lieu(row.adresse_raw, indexes)
        lignes.append({
            "patient_id": str(row.patient_id),
            "district": item["district"] if item else VALEUR_INCONNUE,
            "commune": item["commune"] if item else VALEUR_INCONNUE,
            "fonkontany": item["fonkontany"] if item else VALEUR_INCONNUE,
            "adresse_raw": str(row.adresse_raw).strip(),
            "match_score": score,
            "match_type": methode,
        })

    columns = ["patient_id", "district", "commune", "fonkontany", "adresse_raw", "match_score", "match_type"]
    result = pd.DataFrame(lignes, columns=columns).drop_duplicates("patient_id")
    if result["patient_id"].duplicated().any():
        raise ValueError("Le seed contient plusieurs lignes pour un même patient_id")
    return result.sort_values("patient_id").reset_index(drop=True)

# ------------------------------------------------------------------
# 4. PIPELINE EXECUTION UNIFIÉ
# ------------------------------------------------------------------

if __name__ == "__main__":
    print(f"1. Chargement et indexation des lieux depuis '{FILE_GAZETTEER}'...")
    indexes = charger_indexes(FILE_GAZETTEER)
    print(f"   -> {len(indexes['communes'])} communes et {len(indexes['fokontany'])} fokontany indexés.")

    print("\n2. Connexion à MariaDB et extraction des adresses...")
    with pymysql.connect(**DB_CONFIG) as conn:
        df_a_traiter = extraire_patients(conn)
    print(f"   -> {len(df_a_traiter)} adresses récupérées de MariaDB.")

    print(f"\n3. Exécution du matching...")
    df_out = construire_seed(df_a_traiter, indexes)
    SEED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(SEED_OUTPUT, index=False, sep=";", encoding="utf-8", lineterminator="\n")

    trouves = (df_out["match_type"] != "NON_TROUVE").sum()
    print(f"\nTerminé avec succès !")
    print(f"   -> {trouves} / {len(df_out)} adresses enrichies.")
    print(f"   -> Fichier seed dbt généré : {SEED_OUTPUT}")