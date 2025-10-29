"""Extract mémoires from UNIL Philosophy Department page."""

from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import (
    RawWebTextBibitem,
    RawWebTextAuthor,
)
from philoch_bib_enhancer.cli.manual_raw_web_text_to_csv import process_raw_bibitems

# Data extracted from https://www.unil.ch/philo/fr/home/menuinst/recherches/memoires.html
# Fetched on 2025-10-29

raw_bibitems = [
    # 2024
    RawWebTextBibitem(
        raw_text="RIZET Océane: Objective Idealism\nJuin 2024\nDirecteur : Esfeld Michael",
        type="mastersthesis",
        title="Objective Idealism",
        year=2024,
        authors=[RawWebTextAuthor(given="Océane", family="RIZET")],
    ),
    RawWebTextBibitem(
        raw_text="STUTZ Rudolf : Normativité, connaissance \"a priori\" et catégories de l'entendement.\nJanvier 2024\nDirecteur : Esfeld Michael",
        type="mastersthesis",
        title="Normativité, connaissance \"a priori\" et catégories de l'entendement",
        year=2024,
        authors=[RawWebTextAuthor(given="Rudolf", family="STUTZ")],
    ),
    RawWebTextBibitem(
        raw_text="VALZINO Alexia : De la croyance à la responsabilité : Réflexion sur l'éthique normative virtuelle de Robert Brandom.\nJuin 2024\nDirecteur : Esfeld Michael",
        type="mastersthesis",
        title="De la croyance à la responsabilité : Réflexion sur l'éthique normative virtuelle de Robert Brandom",
        year=2024,
        authors=[RawWebTextAuthor(given="Alexia", family="VALZINO")],
    ),
    RawWebTextBibitem(
        raw_text="KREBS Théo : Le Paradoxe pirandellien, drame et liberté sur scène : exploration et hypothèses sur l'écriture et les pratiques théâtrales.\nAoût 2024\nDirecteur : Groneberg Michael",
        type="mastersthesis",
        title="Le Paradoxe pirandellien, drame et liberté sur scène : exploration et hypothèses sur l'écriture et les pratiques théâtrales",
        year=2024,
        authors=[RawWebTextAuthor(given="Théo", family="KREBS")],
    ),
    RawWebTextBibitem(
        raw_text="SAUCY Nicolas : De l'Absolu à l'esthétique eudémonique: de l'influence d'Hegel et Schopenhauer sur Balzac et Zola.\nJanvier 2024\nDirecteur : Groneberg Michael",
        type="mastersthesis",
        title="De l'Absolu à l'esthétique eudémonique: de l'influence d'Hegel et Schopenhauer sur Balzac et Zola",
        year=2024,
        authors=[RawWebTextAuthor(given="Nicolas", family="SAUCY")],
    ),
    RawWebTextBibitem(
        raw_text="GIRARDIER Valentine : Entre utopie et idéologie, comment l'imaginaire d'Internet façonne la culture technique contemporaine. Juin 2024\nDirectrice : Maigné Carole",
        type="mastersthesis",
        title="Entre utopie et idéologie, comment l'imaginaire d'Internet façonne la culture technique contemporaine",
        year=2024,
        authors=[RawWebTextAuthor(given="Valentine", family="GIRARDIER")],
    ),
    RawWebTextBibitem(
        raw_text="GRABER Yoachim : Art, geste, symbole ; le geste artistique et la danse selon Susanne K. Langer.\nJuin 2024\nDirectrice : Maigné Carole",
        type="mastersthesis",
        title="Art, geste, symbole ; le geste artistique et la danse selon Susanne K. Langer",
        year=2024,
        authors=[RawWebTextAuthor(given="Yoachim", family="GRABER")],
    ),
    RawWebTextBibitem(
        raw_text="PORTILLO FERNANDEZ Victor : Au sujet de la parole, de la parole au sujet. La parole comme lieu d'émergence du sujet chez Merleau-Ponty, Benveniste, Ricoeur et Lacan.\nJuin 2024\nDirectrice : Maigné Carole",
        type="mastersthesis",
        title="Au sujet de la parole, de la parole au sujet. La parole comme lieu d'émergence du sujet chez Merleau-Ponty, Benveniste, Ricoeur et Lacan",
        year=2024,
        authors=[RawWebTextAuthor(given="Victor", family="PORTILLO FERNANDEZ")],
    ),
    RawWebTextBibitem(
        raw_text="L'EPLATTENIER Margaux : LLM et langage: Investigations philosophiques et statistiques.\nJanvier 2024\nDirecteur : Picca Davide",
        type="mastersthesis",
        title="LLM et langage: Investigations philosophiques et statistiques",
        year=2024,
        authors=[RawWebTextAuthor(given="Margaux", family="L'EPLATTENIER")],
    ),
    RawWebTextBibitem(
        raw_text="RICHARDET Bastien : Des conditions de l'émancipation. Le problème de l'abolition de la domination dans le cadre d'une critique catégorielle du patriarcat marchand.\nJuin 2024\nDirecteur : Poltier Hugues",
        type="mastersthesis",
        title="Des conditions de l'émancipation. Le problème de l'abolition de la domination dans le cadre d'une critique catégorielle du patriarcat marchand",
        year=2024,
        authors=[RawWebTextAuthor(given="Bastien", family="RICHARDET")],
    ),
    RawWebTextBibitem(
        raw_text="BEHBAHANI ZADEH Kimiya : De la technique à la connaissance : traitement canguilhémien de la métaphore de la machine.\nAoût 2024\nDirecteur : Sachse Christian",
        type="mastersthesis",
        title="De la technique à la connaissance : traitement canguilhémien de la métaphore de la machine",
        year=2024,
        authors=[RawWebTextAuthor(given="Kimiya", family="BEHBAHANI ZADEH")],
    ),
    RawWebTextBibitem(
        raw_text="DORDOLO Sofia : Les Intelligences Artificielles peuvent-elles ressentir ?.\nJuin 2024\nDirecteur : Sachse Christian",
        type="mastersthesis",
        title="Les Intelligences Artificielles peuvent-elles ressentir ?",
        year=2024,
        authors=[RawWebTextAuthor(given="Sofia", family="DORDOLO")],
    ),
    RawWebTextBibitem(
        raw_text="LESSENE-YAGBALE Joël-Melchi: Peut-on parvenir à une définition claire et précise de la conscience en utilisant comme cadre de recherche la théorie de l'évolution ?\nJanvier 2024\nDirecteur : Sachse Christian",
        type="mastersthesis",
        title="Peut-on parvenir à une définition claire et précise de la conscience en utilisant comme cadre de recherche la théorie de l'évolution ?",
        year=2024,
        authors=[RawWebTextAuthor(given="Joël-Melchi", family="LESSENE-YAGBALE")],
    ),
    RawWebTextBibitem(
        raw_text="MACHEREL Gregory : Réaffirmation d'une autonomie explicative de la biologie dans le contexte de la biologie quantique.\nJuin 2024\nDirecteur : Sachse Christian",
        type="mastersthesis",
        title="Réaffirmation d'une autonomie explicative de la biologie dans le contexte de la biologie quantique",
        year=2024,
        authors=[RawWebTextAuthor(given="Gregory", family="MACHEREL")],
    ),
    RawWebTextBibitem(
        raw_text="DELIYANIDIS Apollon : \"Apologie de Socrate\" : la quête divine et son exécution qui dérangent Athènes.\nJanvier 2024\nDirectrice : Schniewind Alexandrine",
        type="mastersthesis",
        title="\"Apologie de Socrate\" : la quête divine et son exécution qui dérangent Athènes",
        year=2024,
        authors=[RawWebTextAuthor(given="Apollon", family="DELIYANIDIS")],
    ),
    RawWebTextBibitem(
        raw_text="DOROGI Romain : Un plus long chemin : Une étude des mythes eschatologiques de Platon.\nJuin 2024\nDirectrice : Schniewind Alexandrine",
        type="mastersthesis",
        title="Un plus long chemin : Une étude des mythes eschatologiques de Platon",
        year=2024,
        authors=[RawWebTextAuthor(given="Romain", family="DOROGI")],
    ),
    RawWebTextBibitem(
        raw_text="LEONE Matteo : La pertinence d'une pratique philosophique dans la réalisation des objectifs du Plan d'Études Romand (PER) : comment la philosophie pour enfants participe au Projet global de formation de l'élève en Suisse romande ?\nJanvier 2024\nDirectrice : Schniewind Alexandrine",
        type="mastersthesis",
        title="La pertinence d'une pratique philosophique dans la réalisation des objectifs du Plan d'Études Romand (PER) : comment la philosophie pour enfants participe au Projet global de formation de l'élève en Suisse romande ?",
        year=2024,
        authors=[RawWebTextAuthor(given="Matteo", family="LEONE")],
    ),
    RawWebTextBibitem(
        raw_text="VIANA GONZALEZ Mikael : Thomas d'Aquin, un philosophe rushdinien ?. Étude comparative des noétiques d'Averroès et de Thomas d'Aquin.\nJuin 2024\nDirectrice : Schniewind Alexandrine",
        type="mastersthesis",
        title="Thomas d'Aquin, un philosophe rushdinien ?. Étude comparative des noétiques d'Averroès et de Thomas d'Aquin",
        year=2024,
        authors=[RawWebTextAuthor(given="Mikael", family="VIANA GONZALEZ")],
    ),
    RawWebTextBibitem(
        raw_text="NICOLE Thibaud : Les écueils de la quête d'épanouissement. Une analyse des relations au monde induites par les discours de développement personnel : aliénation, désenchantement et romantisme.\nJuin 2024\nDirectrice : Zurbuchen Pittlik Simone",
        type="mastersthesis",
        title="Les écueils de la quête d'épanouissement. Une analyse des relations au monde induites par les discours de développement personnel : aliénation, désenchantement et romantisme",
        year=2024,
        authors=[RawWebTextAuthor(given="Thibaud", family="NICOLE")],
    ),
]

if __name__ == "__main__":
    print(f"Extracting {len(raw_bibitems)} mémoires from UNIL...")
    process_raw_bibitems(
        raw_bibitems=raw_bibitems,
        output_path="./data/test-1/unil_memoires_2024.csv",
    )
    print("✓ Extraction complete!")
