# SEO Position Checker

Un outil web pour suivre le positionnement d'un site sur Google.fr. Tu entres un domaine + une liste de mots-cles, il te dit a quelle position ton site apparait dans les resultats Google pour chaque mot-cle. Les resultats sont stockes en base de donnees et exportables en Excel.

---

## Comment ca marche (vue d'ensemble)

L'application est composee de **3 parties** qui communiquent entre elles :

```
 +-----------------+         +------------------+         +-----------+
 |    FRONTEND     |  <--->  |     BACKEND      |  <--->  |  DATABASE |
 |  (index.html)   |  HTTP   |  (Flask / Python) |  SQL    |  (SQLite) |
 |  dans le        |         |  app.py          |         | positions |
 |  navigateur     |         |  scraper.py      |         |   .db     |
 +-----------------+         +------------------+         +-----------+
                                     |
                                     | API calls
                                     v
                              +--------------+
                              |   SerpAPI    |
                              | (Google.fr)  |
                              +--------------+
```

1. **Le frontend** (ce que tu vois dans le navigateur) envoie des requetes au backend
2. **Le backend** (le serveur Python) recoit ces requetes, interroge Google via SerpAPI, et stocke les resultats
3. **La base de donnees** (un fichier SQLite) garde l'historique de toutes les positions

---

## Structure du projet

```
seo-position/
├── .env                    # Ta cle API SerpAPI (secret, pas sur GitHub)
├── .gitignore              # Fichiers a ne pas envoyer sur GitHub
├── backend/
│   ├── app.py              # Le serveur web (Flask) - le chef d'orchestre
│   ├── scraper.py          # Le module qui interroge Google via SerpAPI
│   ├── database.py         # Le module qui gere la base de donnees SQLite
│   └── requirements.txt    # La liste des librairies Python necessaires
├── frontend/
│   └── index.html          # Toute l'interface web (HTML + CSS + JavaScript)
└── data/
    └── positions.db        # La base de donnees (creee automatiquement)
```

---

## Explication de chaque fichier

### `backend/app.py` — Le serveur web

C'est le **coeur de l'application**. Il fait tourner un serveur web avec Flask (une librairie Python pour creer des sites/API).

**Ce qu'il fait :**

- **Sert la page web** : quand tu vas sur `http://localhost:5001`, il envoie le fichier `index.html` a ton navigateur
- **Expose une API REST** : des URLs que le frontend appelle pour lire/ecrire des donnees

**Les routes (URLs) de l'API :**

| Methode | URL | Ce que ca fait |
|---------|-----|----------------|
| `GET` | `/` | Affiche la page web |
| `GET` | `/api/settings` | Recupere le domaine cible enregistre |
| `POST` | `/api/settings` | Enregistre un nouveau domaine cible |
| `GET` | `/api/keywords` | Liste tous les mots-cles |
| `POST` | `/api/keywords` | Ajoute un ou plusieurs mots-cles |
| `DELETE` | `/api/keywords/3` | Supprime le mot-cle avec l'id 3 |
| `POST` | `/api/keywords/clear` | Supprime tous les mots-cles |
| `POST` | `/api/check` | Lance un scan (en arriere-plan) |
| `GET` | `/api/status` | Verifie si un scan est en cours + progression |
| `GET` | `/api/results` | Recupere les derniers resultats |
| `GET` | `/api/history/3` | Historique des positions du mot-cle id 3 |
| `GET` | `/api/export` | Telecharge un fichier Excel des resultats |

**Concepts importants dans ce fichier :**

- **`@app.route(...)`** : C'est un "decorateur" Flask. Il dit "quand quelqu'un visite cette URL, execute cette fonction". Par exemple :
  ```python
  @app.route("/api/settings", methods=["GET"])
  def api_get_settings():
      domain = get_setting("target_domain") or ""
      return jsonify({"target_domain": domain})
  ```
  Quand le navigateur appelle `GET /api/settings`, Flask execute `api_get_settings()` et renvoie du JSON.

- **`threading.Thread`** : Le scan peut prendre du temps (quelques secondes par mot-cle). Pour ne pas bloquer le serveur, on le lance dans un **thread** (un processus parallele). Comme ca, le serveur continue de repondre pendant que le scan tourne.

- **`scan_state`** : Un dictionnaire global qui stocke l'etat du scan en cours (quel mot-cle est en train d'etre verifie, combien il y en a au total, etc.). Le frontend interroge `/api/status` toutes les 3 secondes pour afficher la progression.

- **`scan_lock`** : Un verrou (Lock) qui empeche de lancer 2 scans en meme temps. Si un scan est deja en cours, le 2eme est refuse.

- **Export Excel** : La route `/api/export` utilise la librairie `openpyxl` pour generer un fichier `.xlsx` en memoire avec les resultats, mis en forme avec des couleurs (vert pour top 3, orange pour top 10, rouge au-dela).

- **Chargement du `.env`** : Les lignes 8-15 lisent le fichier `.env` a la racine du projet et chargent les variables d'environnement (comme `SERPAPI_KEY`). Ca permet de garder les secrets hors du code.

---

### `backend/scraper.py` — L'interrogation de Google

Ce fichier contient la logique pour chercher sur Google.fr et trouver la position d'un domaine.

**Comment ca marche :**

1. On envoie une requete a **SerpAPI** (un service payant qui interroge Google a notre place et renvoie les resultats en JSON propre)
2. On recoit la liste des resultats organiques (les vrais resultats, pas les pubs)
3. On parcourt chaque resultat et on compare le domaine trouve avec notre domaine cible
4. Si on le trouve, on retourne sa position + l'URL exacte. Sinon, on retourne `(None, None)`

**Pourquoi SerpAPI et pas scraper Google directement ?**
Google bloque les requetes automatisees (CAPTCHAs, blocage IP). SerpAPI contourne ce probleme en utilisant son propre reseau de serveurs. C'est fiable et ca marche a chaque fois.

**Les fonctions :**

- **`scrape_google(keyword, target_domain)`** : Fait la recherche Google.fr pour un mot-cle et cherche le domaine dans les 100 premiers resultats
- **`check_keyword(keyword, target_domain)`** : Appelle `scrape_google` avec une logique de retry (si ca echoue, on reessaie une fois apres 5 secondes)
- **`delay_between_keywords()`** : Attend 2 a 5 secondes entre chaque recherche pour ne pas surcharger l'API

---

### `backend/database.py` — La base de donnees

Ce fichier gere tout ce qui touche au stockage des donnees avec **SQLite** (une base de donnees legere stockee dans un seul fichier).

**Les 3 tables :**

```
settings         keywords              positions
+---------+      +------------+        +-------------+
| key     |      | id         |        | id          |
| value   |      | keyword    |        | keyword_id  | --> lien vers keywords.id
+---------+      | created_at |        | position    |
                 +------------+        | url_found   |
                                       | checked_at  |
                                       +-------------+
```

- **`settings`** : Stocke la configuration (le domaine cible). C'est un simple tableau cle/valeur.
- **`keywords`** : La liste des mots-cles a surveiller. Chaque mot-cle est unique (pas de doublons).
- **`positions`** : L'historique des resultats. Chaque fois qu'on scanne un mot-cle, on ajoute une ligne ici. Ca permet de suivre l'evolution dans le temps.

**Les fonctions :**

| Fonction | Ce qu'elle fait |
|----------|----------------|
| `init_db()` | Cree les tables si elles n'existent pas encore |
| `get_setting(key)` | Lit une valeur dans la table settings |
| `set_setting(key, value)` | Ecrit/met a jour une valeur dans settings |
| `get_keywords()` | Renvoie tous les mots-cles |
| `add_keyword(keyword)` | Ajoute un mot-cle (renvoie `None` si doublon) |
| `delete_keyword(id)` | Supprime un mot-cle et tout son historique |
| `save_position(keyword_id, position, url)` | Enregistre le resultat d'un scan |
| `get_latest_positions()` | Renvoie le dernier resultat pour chaque mot-cle |
| `get_history(keyword_id)` | Renvoie tout l'historique d'un mot-cle |

**Concept : la requete SQL de `get_latest_positions()`**
```sql
SELECT k.id, k.keyword, p.position, p.url_found, p.checked_at
FROM keywords k
LEFT JOIN positions p ON p.id = (
    SELECT p2.id FROM positions p2
    WHERE p2.keyword_id = k.id
    ORDER BY p2.checked_at DESC LIMIT 1
)
```
En francais : "Pour chaque mot-cle, va chercher la position la plus recente". Le `LEFT JOIN` garantit qu'on affiche aussi les mots-cles qui n'ont pas encore ete scannes (avec des valeurs `NULL`).

---

### `frontend/index.html` — L'interface web

C'est un **seul fichier HTML** qui contient tout : la structure (HTML), le style (CSS), et le comportement (JavaScript).

**Les 3 pages (dans le meme fichier) :**

1. **Nouvelle analyse** : Formulaire pour entrer le domaine + coller une liste de mots-cles + bouton "Lancer"
2. **Resultats** : Tableau avec les positions (badges colores) + bouton pour telecharger en Excel
3. **Historique** : Graphique Chart.js montrant l'evolution de la position d'un mot-cle dans le temps

**Comment ca communique avec le backend :**

Le JavaScript utilise `fetch()` pour appeler l'API :
```javascript
// Exemple : recuperer les resultats
const results = await fetch('/api/results').then(r => r.json());
```

Le frontend n'a aucune donnee en local — tout vient du backend a chaque chargement de page.

**Le systeme de navigation :**

Les 3 "pages" sont en fait des `<div>` qui s'affichent/se cachent avec CSS (`display: none` / `display: block`). Quand tu cliques sur un lien dans la sidebar, la fonction `showPage('results')` cache toutes les pages et affiche celle demandee.

**Le scan en temps reel :**

Quand un scan est en cours, le frontend appelle `GET /api/status` toutes les 3 secondes (avec `setInterval`) pour mettre a jour la barre de progression et afficher quel mot-cle est en cours de verification.

---

### `.env` — Les secrets

```
SERPAPI_KEY=ta_cle_api_ici
```

Ce fichier contient ta cle API SerpAPI. Il est dans `.gitignore` donc il n'est **jamais envoye sur GitHub**. Chaque personne qui clone le projet doit creer son propre `.env`.

---

### `requirements.txt` — Les dependances

Liste des librairies Python necessaires :

| Librairie | A quoi elle sert |
|-----------|-----------------|
| `Flask` | Serveur web / API |
| `requests` | Faire des requetes HTTP (utilise par SerpAPI) |
| `beautifulsoup4` | Parser du HTML (gardee pour compatibilite) |
| `lxml` | Parseur HTML rapide (utilisee par BeautifulSoup) |
| `openpyxl` | Generer des fichiers Excel (.xlsx) |
| `google-search-results` | Client Python officiel pour SerpAPI |

---

## Installation pas a pas

### Prerequis

- **Python 3.8+** installe sur ton ordinateur ([telecharger ici](https://www.python.org/downloads/))
- **Un compte SerpAPI** avec une cle API ([creer un compte gratuit ici](https://serpapi.com/) — 100 recherches/mois gratuites)

### Etape 1 : Cloner le projet

```bash
git clone https://github.com/sylv1SENG/seo-position.git
cd seo-position
```

### Etape 2 : Installer les dependances Python

```bash
pip install -r backend/requirements.txt
```

Ca telecharge et installe toutes les librairies listees dans `requirements.txt`.

### Etape 3 : Configurer ta cle API

Cree un fichier `.env` a la racine du projet :

```bash
echo "SERPAPI_KEY=ta_cle_api_serpapi_ici" > .env
```

Remplace `ta_cle_api_serpapi_ici` par ta vraie cle depuis [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key).

### Etape 4 : Lancer l'application

```bash
cd backend
python app.py
```

Tu devrais voir :
```
 * Running on http://127.0.0.1:5001
```

### Etape 5 : Ouvrir dans le navigateur

Va sur **http://localhost:5001**

### Etape 6 : Utiliser

1. Sur la page "Nouvelle analyse", entre ton domaine (ex: `monsite.com`)
2. Colle ta liste de mots-cles (un par ligne) dans le champ texte
3. Clique sur **Lancer l'analyse**
4. Attends que le scan finisse (~5 secondes par mot-cle)
5. Va sur **Resultats** pour voir les positions
6. Clique sur **Telecharger Excel** pour obtenir le rapport

---

## Les couleurs des positions

| Position | Couleur | Signification |
|----------|---------|---------------|
| #1 a #3 | Vert | Excellent, top 3 Google |
| #4 a #10 | Orange | Bonne premiere page |
| #11+ | Rouge | Au-dela de la premiere page |
| N/A | Gris | Domaine non trouve dans le top 100 |

---

## FAQ

**Q: C'est quoi SerpAPI ?**
Un service qui interroge Google a ta place et te renvoie les resultats proprement en JSON. Google bloque les robots, mais SerpAPI a des serveurs qui gerent ca. 100 recherches gratuites par mois.

**Q: Pourquoi le port 5001 et pas 5000 ?**
Sur macOS, le port 5000 est souvent utilise par AirPlay Receiver. On utilise 5001 pour eviter le conflit.

**Q: Ou sont stockees les donnees ?**
Dans le fichier `data/positions.db`. C'est un fichier SQLite, tu peux le supprimer pour repartir de zero.

**Q: Je peux changer le pays de recherche ?**
Oui, dans `scraper.py`, modifie `google_domain`, `gl` et `hl` dans les parametres SerpAPI. Par exemple pour Google.com US : `google_domain: "google.com"`, `gl: "us"`, `hl: "en"`.
