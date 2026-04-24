# ÉnergieData Cameroun

Plateforme nationale de collecte, d'analyse et de visualisation des données de consommation électrique des ménages camerounais.

## Caractéristiques

- **Collecte de données** : Formulaire public pour soumettre la consommation électrique mensuelle
- **Calcul automatique de factures** : Tarification ENEO (50 FCFA/kWh jusqu'à 110 kWh, 79 FCFA/kWh au-delà)
- **Tableau de bord analytique** : Statistiques nationales et régionales en temps réel
- **Analyses avancées** : Tendances mensuelles, distributions, statistiques descriptives
- **Estimation des besoins** : Projections des besoins énergétiques par région
- **Export de données** : Téléchargement en CSV
- **Couverture complète** : 10 régions du Cameroun
- **100% public** : Aucune authentification requise

## Stack technologique

- **Backend** : Flask (Python 3)
- **Frontend** : HTML5, CSS3, JavaScript vanilla
- **Base de données** : SQLite (développement) / PostgreSQL (production)
- **Visualisations** : Chart.js
- **Déploiement** : Render.com

## Installation locale

### Prérequis

- Python 3.8+
- pip

### Étapes

1. **Cloner le repository**
   ```bash
   git clone <repository-url>
   cd energie-cameroun
   ```

2. **Créer un environnement virtuel**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows: venv\Scripts\activate
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Lancer l'application**
   ```bash
   python app.py
   ```

5. **Accéder à l'application**
   - Ouvrir http://localhost:5000 dans votre navigateur

## Déploiement sur Render

### Étapes

1. **Créer un compte sur Render.com**
   - Aller sur https://render.com

2. **Connecter votre repository GitHub**
   - Autoriser Render à accéder à votre compte GitHub

3. **Créer un nouveau Web Service**
   - Cliquer sur "New +" → "Web Service"
   - Sélectionner votre repository
   - Configurer les paramètres :
     - **Name** : energie-cameroun
     - **Environment** : Python 3
     - **Build Command** : `pip install -r requirements.txt`
     - **Start Command** : `gunicorn app:app`
     - **Instance Type** : Free (ou payant selon vos besoins)

4. **Configurer les variables d'environnement**
   - Ajouter dans "Environment" :
     - `FLASK_ENV` : production
     - `DATABASE_URL` : (laisser vide pour SQLite, ou ajouter une URL PostgreSQL)

5. **Déployer**
   - Cliquer sur "Create Web Service"
   - Render déploiera automatiquement votre application

## Structure du projet

```
energie-cameroun/
├── app.py                 # Application Flask principale
├── requirements.txt       # Dépendances Python
├── Procfile              # Configuration Render
├── templates/            # Templates HTML
│   ├── index.html        # Landing page
│   ├── submit.html       # Formulaire de soumission
│   ├── dashboard.html    # Tableau de bord
│   ├── data.html         # Tableau de données
│   ├── analytics.html    # Analyses avancées
│   ├── regions.html      # Besoins régionaux
│   ├── 404.html          # Page 404
│   └── 500.html          # Page 500
├── static/               # Fichiers statiques
│   └── css/
│       └── style.css     # Styles globaux
└── README.md             # Ce fichier
```

## API Endpoints

### Consommation

- `POST /submit` - Soumettre une nouvelle consommation
- `POST /api/consumption/preview-bill` - Aperçu de la facture
- `GET /api/consumption/list` - Lister les consommations (avec filtres)
- `GET /api/consumption/stats-by-region` - Statistiques par région
- `GET /api/consumption/national-stats` - Statistiques nationales
- `GET /api/consumption/monthly-trends` - Tendances mensuelles
- `GET /api/consumption/distribution` - Distribution des consommations
- `GET /api/consumption/region-needs` - Estimation des besoins régionaux
- `GET /api/consumption/export-csv` - Export en CSV

## Tarification ENEO

La tarification suit le barème officiel ENEO :

- **Tranche 1** : 0–110 kWh → 50 FCFA/kWh
- **Tranche 2** : > 110 kWh → 79 FCFA/kWh

Exemple : Pour 150 kWh
- Tranche 1 : 110 × 50 = 5 500 FCFA
- Tranche 2 : 40 × 79 = 3 160 FCFA
- **Total : 8 660 FCFA**

## Régions couvertes

1. Adamaoua
2. Centre
3. Est
4. Extrême-Nord
5. Littoral
6. Nord
7. Nord-Ouest
8. Ouest
9. Sud
10. Sud-Ouest

## Licence

MIT

## Contact

Pour toute question ou contribution, veuillez créer une issue sur GitHub.
