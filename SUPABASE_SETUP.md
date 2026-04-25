# Configuration Supabase

## Problème Actuel

La clé API Supabase fournie semble **tronquée ou invalide**:

```
SUPABASE_KEY=sb_publishable_Tw_ucAoJj5LT09l8a1zy0g_7ON7D4bz
```

## Solution: Obtenir la Clé API Correcte

### Étape 1: Accéder à Supabase

1. Allez sur [https://app.supabase.com](https://app.supabase.com)
2. Connectez-vous à votre compte

### Étape 2: Sélectionner le Projet

3. Sélectionnez le projet **`mxwqyaghxnpxkfffebeu`**

### Étape 3: Récupérer les Clés API

4. Allez à **Settings > API**
5. Vous verrez plusieurs clés:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** → `SUPABASE_KEY` (c'est celle-ci)
   - **service_role secret** → NE PAS UTILISER en frontend

### Étape 4: Copier la Clé Complète

6. Copiez la clé **"anon public"** en entier (elle devrait faire environ 150-200 caractères)
   - La clé commence par: `eyJhbGciOi...` ou `sb_...`
   - Assurez-vous de copier TOUTE la clé

### Étape 5: Mettre à Jour .env

7. Ouvrez le fichier `.env`:

   ```
   SUPABASE_URL=https://mxwqyaghxnpxkfffebeu.supabase.co
   SUPABASE_KEY=[VOTRE_CLÉ_ANON_COMPLÈTE]
   FLASK_ENV=development
   PORT=5000
   ```

8. Remplacez `[VOTRE_CLÉ_ANON_COMPLÈTE]` par la clé exacte copiée depuis Supabase

### Étape 6: Vérifier la Configuration

9. Testez la connexion:

   ```bash
   source venv/bin/activate
   python3 app.py
   ```

   Vous devriez voir:

   ```
   ✅ Supabase connection test passed
   📊 Database URL: https://mxwqyaghxnpxkfffebeu.supabase.co...
   🚀 Starting Flask app on port 5000
   ```

## Dépannage

### Erreur: "Invalid API key"

- Vérifiez que vous avez copié la CLÉE **anon public** complète (pas la clé "service_role")
- Vérifiez qu'il n'y a pas d'espaces au début ou à la fin

### Erreur: "Network error"

- Vérifiez votre connexion Internet
- Vérifiez que le project_id `mxwqyaghxnpxkfffebeu` est correct

### Les données ne s'affichent pas

- Assurez-vous que la table `consumption_records` existe dans Supabase
- Vérifiez les permissions d'accès de la clé anon public dans Supabase

## Structure de Données Requise

La table `consumption_records` doit avoir ces colonnes:

```
- id (bigint, primary key, auto-increment)
- region (text)
- month (integer)
- year (integer)
- kwh (real/float)
- bill_amount (real/float)
- household_size (integer)
- submitter_name (text, default: 'Anonyme')
- created_at (timestamp with timezone, default: now())
```

## Lancer l'Application

Une fois la configuration terminée:

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Installer les dépendances (optionnel, déjà installées)
pip install -r requirements.txt

# Démarrer l'application
python3 app.py
```

L'app démarrera à `http://localhost:5000`
