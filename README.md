# ÉnergieData Cameroun

Plateforme nationale de collecte, d'analyse et de visualisation des données de consommation électrique des ménages camerounais.

## Caractéristiques

- **Collecte de données** : Formulaire public pour soumettre la consommation électrique mensuelle
- **Calcul automatique de factures** : Tarification ENEO (50 FCFA/kWh jusqu'à 110 kWh, 79 FCFA/kWh au-delà)
- **Tableau de bord analytique** : Statistiques nationales et régionales en temps réel
- **Analyses avancées** :
  - Régression linéaire simple et multiple pour prédiction de consommation
  - Classification supervisée (Random Forest) pour catégorisation (Faible/Moyen/Élevé)
  - Segmentation régionale par K-means clustering
  - Statistiques descriptives complètes (Q1, Q3, IQR, asymétrie, aplatissement)
  - Matrice de corrélation entre variables
- **Zones de prédiction interactives** : Estimez la consommation ou catégorie basée sur région, mois, taille ménage
- **Export PDF** : Génération de rapports d'analyse complets
- **Estimation des besoins** : Projections des besoins énergétiques par région
- **Export de données** : Téléchargement en CSV
- **Couverture complète** : 10 régions du Cameroun
- **100% public** : Aucune authentification requise

## Stack technologique

- **Backend** : Flask (Python 3) avec SQLAlchemy ORM
- **Frontend** : HTML5, CSS3, JavaScript vanilla
- **Machine Learning** : scikit-learn (régression, classification, clustering)
- **Visualisations** : Chart.js
- **Rapports** : ReportLab (PDF)
- **Données** : Pandas, NumPy, SciPy
- **Base de données** : SQLite (développement) / PostgreSQL (production)
- **Déploiement** : Render.com

## Installation locale

### Prérequis

- Python 3.8+
- pip

### Étapes

1. **Cloner le repository**

   ```bash
   git clone https://github.com/NOVA-X-Code/TP-INF232-EC2.git
   cd "Data Analysis and Energy Consumption App Development"
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

4. **Initialiser la base de données (optionnel)**

   ```bash
   python seed_data.py
   ```

5. **Lancer l'application**

   ```bash
   python app.py
   ```

6. **Accéder à l'application**
   - Ouvrir http://localhost:5000 dans votre navigateur

## Structure du projet

```
Data Analysis and Energy Consumption App Development/
├── app.py                  # Application Flask principale avec routes et analyses
├── seed_data.py           # Script de génération de données de test
├── requirements.txt       # Dépendances Python
├── Procfile               # Configuration Render
├── README.md              # Ce fichier
├── templates/             # Templates HTML
│   ├── index.html         # Landing page
│   ├── submit.html        # Formulaire de soumission
│   ├── dashboard.html     # Tableau de bord avec statistiques
│   ├── data.html          # Tableau de données complet
│   ├── analytics.html     # Analyses simples et prédictions
│   ├── advanced-analysis.html  # Analyses avancées (régression, classification, segmentation)
│   ├── regions.html       # Besoins régionaux par région
│   ├── regression-simple.html  # Page détaillée régression simple
│   ├── 404.html           # Page 404
│   └── 500.html           # Page 500 erreur serveur
├── static/                # Fichiers statiques
│   ├── css/
│   │   ├── style.css      # Styles globaux
│   │   └── index.css      # Styles index
│   └── js/
│       └── mobile-menu.js # Menu mobile responsive
└── instance/              # Dossier instance (données BD)
    └── energie_cameroun.db # Base de données SQLite
```

## API Endpoints

### Consommation

- `POST /submit` - Soumettre une nouvelle consommation
- `POST /api/consumption/preview-bill` - Aperçu de la facture
- `GET /api/consumption/list` - Lister les consommations (avec filtres)
- `GET /api/consumption/stats-by-region` - Statistiques par région
- `GET /api/consumption/national-stats` - Statistiques nationales
- `GET /api/consumption/monthly-trends` - Tendances mensuelles

### Analyses

- `GET /api/analysis/regression-simple` - Régression linéaire simple (household_size → kwh)
- `GET /api/analysis/regression-multiple` - Régression multiple (région, mois, household_size → kwh)
- `GET /api/analysis/classification` - Classification supervisée (prédiction catégorie)
- `GET /api/analysis/clustering` - Segmentation régionale par K-means (3 groupes)
- `GET /api/analysis/advanced-stats` - Statistiques descriptives avancées
- `GET /api/analysis/anova` - Test ANOVA (internal, non exposé en UI)
- `GET /api/analysis/correlation-matrix` - Matrice de corrélation

### Export

- `GET /api/consumption/export-csv` - Export en CSV
- `GET /api/export-pdf/<analysis_type>` - Export en PDF (types: simple, multiple, classification, clustering, statistics)

## Modèles d'analyse

### Régression linéaire simple

Prédit la consommation (kWh) en fonction de la taille du ménage.

- **Équation** : kWh = intercept + slope × household_size
- **Métrique** : R² (coefficient de détermination)

### Régression linéaire multiple

Prédit la consommation en fonction de région, mois et taille ménage.

- **Entrées** : région, mois (1-12), taille ménage (1-50)
- **Sortie** : consommation estimée (kWh)
- **Zone prédiction** : Interface interactive pour tester

### Classification supervisée

Catégorise la consommation en Faible/Moyen/Élevé.

- **Algorithme** : Random Forest Classifier
- **Entrées** : région, mois, taille ménage
- **Sortie** : catégorie de consommation avec code couleur
- **Zone prédiction** : Interface interactive

### Segmentation régionale (K-means)

Groupe automatiquement les 10 régions en 3 profils énergétiques.

- **Algorithme** : K-means clustering
- **Critères** : moyenne de consommation (kwh_mean) et écart-type (kwh_std)
- **Résultat** : Groupe 0 (faible), Groupe 1 (moyen), Groupe 2 (fort) triés automatiquement
- **Profils** : Faible (<50 kWh), Moyen (50-100 kWh), Forte (>100 kWh)

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

## Déploiement sur Render

### Étapes

1. **Créer un compte sur Render.com**
   - Aller sur https://render.com

2. **Connecter le repository GitHub**
   - Autoriser Render à accéder à https://github.com/NOVA-X-Code/TP-INF232-EC2.git

3. **Créer un nouveau Web Service**
   - Cliquer sur "New +" → "Web Service"
   - Sélectionner le repository
   - Configurer les paramètres :
     - **Name** : energie-cameroun
     - **Environment** : Python 3
     - **Build Command** : `pip install -r requirements.txt`
     - **Start Command** : `gunicorn app:app`
     - **Instance Type** : Free (ou payant selon les besoins)

4. **Configurer les variables d'environnement**
   - Ajouter dans "Environment" :
     - `FLASK_ENV` : production
     - `DATABASE_URL` : (optionnel, sinon SQLite)

5. **Déployer**
   - Cliquer sur "Create Web Service"
   - Render déploiera automatiquement

## Repository

- **GitHub** : https://github.com/NOVA-X-Code/TP-INF232-EC2.git

## Licence

MIT

## Contact & Contribution

Pour toute question, contribution ou problème, veuillez créer une issue sur le repository GitHub.
