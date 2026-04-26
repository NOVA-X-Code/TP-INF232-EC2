"""
ÉnergieData Cameroun - Application web python Flask
Plateforme de collecte et d'analyse des données de consommation électrique
Avec Supabase comme DataBase
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
from supabase import create_client, Client
from datetime import datetime
import os
import statistics
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from dotenv import load_dotenv

# ─── Load Environment ─────────────────────────────────────────────────────

load_dotenv()

# ─── Configuration ─────────────────────────────────────────────────────────

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize Supabase: {str(e)}")
        print("    Make sure SUPABASE_URL and SUPABASE_KEY are correct in .env")
else:
    raise ValueError("❌ SUPABASE_URL and SUPABASE_KEY environment variables are required!")

# ─── Constants ─────────────────────────────────────────────────────────────

REGIONS = [
    "Adamaoua", "Centre", "Est", "Extrême-Nord", "Littoral",
    "Nord", "Nord-Ouest", "Ouest", "Sud", "Sud-Ouest"
]

MONTHS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

# ENEO Tariff: 50 FCFA/kWh for first 110 kWh, 79 FCFA/kWh beyond
TARIFF_THRESHOLD = 110
TARIFF_LOW = 50
TARIFF_HIGH = 79

# ─── Utility Functions ─────────────────────────────────────────────────────

def calculate_bill(kwh):
    """Calculate electricity bill using ENEO tariff structure."""
    if kwh <= TARIFF_THRESHOLD:
        return kwh * TARIFF_LOW
    else:
        return TARIFF_THRESHOLD * TARIFF_LOW + (kwh - TARIFF_THRESHOLD) * TARIFF_HIGH

def get_bill_breakdown(kwh):
    """Get bill breakdown by tariff tier."""
    tranche1 = min(kwh, TARIFF_THRESHOLD) * TARIFF_LOW
    tranche2 = max(0, kwh - TARIFF_THRESHOLD) * TARIFF_HIGH
    return {
        'tranche1': tranche1,
        'tranche2': tranche2,
        'total': tranche1 + tranche2
    }

def calculate_stats(records):
    """Calculate descriptive statistics for a list of kWh values."""
    if not records:
        return {
            'count': 0,
            'total_kwh': 0,
            'avg_kwh': 0,
            'median_kwh': 0,
            'min_kwh': 0,
            'max_kwh': 0,
            'std_dev_kwh': 0,
            'total_bill': 0,
            'avg_bill': 0,
        }
    
    kwh_values = [r['kwh'] for r in records]
    bill_values = [r['bill_amount'] for r in records]
    
    return {
        'count': len(records),
        'total_kwh': sum(kwh_values),
        'avg_kwh': sum(kwh_values) / len(kwh_values),
        'median_kwh': statistics.median(kwh_values),
        'min_kwh': min(kwh_values),
        'max_kwh': max(kwh_values),
        'std_dev_kwh': statistics.stdev(kwh_values) if len(kwh_values) > 1 else 0,
        'total_bill': sum(bill_values),
        'avg_bill': sum(bill_values) / len(bill_values),
    }

# ─── Routes ────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return "ok", 200
    
@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    """Serve favicon - return a simple 1x1 transparent PNG to avoid 404 errors."""
    # Base64 encoded 1x1 transparent PNG
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    from flask import Response
    return Response(png_data, mimetype='image/png')

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    """Submission form page."""
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validate input
            region = data.get('region')
            month = int(data.get('month', 0))
            year = int(data.get('year', 0))
            kwh = float(data.get('kwh', 0))
            household_size = int(data.get('household_size', 0))
            submitter_name = data.get('submitter_name', 'Anonyme')
            
            if not region or region not in REGIONS:
                return jsonify({'error': 'Région invalide'}), 400
            if month < 1 or month > 12:
                return jsonify({'error': 'Mois invalide'}), 400
            if year < 2000 or year > 2100:
                return jsonify({'error': 'Année invalide'}), 400
            if kwh <= 0 or kwh > 100000:
                return jsonify({'error': 'Consommation invalide'}), 400
            if household_size < 1 or household_size > 50:
                return jsonify({'error': 'Taille du ménage invalide'}), 400
            
            # Calculate bill
            bill_amount = calculate_bill(kwh)
            
            # Save to Supabase
            response = supabase.table('consumption_records').insert({
                'region': region,
                'month': month,
                'year': year,
                'kwh': kwh,
                'bill_amount': bill_amount,
                'household_size': household_size,
                'submitter_name': submitter_name or 'Anonyme',
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            if response.data:
                record_id = response.data[0]['id']
                return jsonify({
                    'success': True,
                    'id': record_id,
                    'bill_amount': bill_amount,
                    'message': 'Consommation soumise avec succès!'
                }), 201
            else:
                return jsonify({'error': 'Erreur lors de la sauvegarde'}), 400
                
        except Exception as e:
            print(f"Error in submit: {str(e)}")
            return jsonify({'error': str(e)}), 400
    
    return render_template('submit.html', regions=REGIONS, months=MONTHS)

@app.route('/dashboard')
def dashboard():
    """Analytics dashboard."""
    return render_template('dashboard.html', regions=REGIONS)

@app.route('/data')
def data_table():
    """Data table and export page."""
    return render_template('data.html', regions=REGIONS, months=MONTHS)

@app.route('/analytics')
def analytics():
    """Advanced analytics page."""
    return render_template('analytics.html', regions=REGIONS)

@app.route('/regions')
def regions_needs():
    """Regional energy needs estimation."""
    return render_template('regions.html')

# ─── API Endpoints ────────────────────────────────────────────────────────

@app.route('/api/consumption/preview-bill', methods=['POST'])
def api_preview_bill():
    """Preview bill calculation."""
    try:
        kwh = float(request.json.get('kwh', 0))
        if kwh <= 0:
            return jsonify({'error': 'kWh must be positive'}), 400
        
        breakdown = get_bill_breakdown(kwh)
        return jsonify(breakdown)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/list', methods=['GET'])
def api_list_consumption():
    """List consumption records with filters."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        region = request.args.get('region')
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        limit = request.args.get('limit', 1000, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Build query
        query = supabase.table('consumption_records').select('*')
        
        if region:
            query = query.eq('region', region)
        if month:
            query = query.eq('month', month)
        if year:
            query = query.eq('year', year)
        
        # Get total count
        count_response = supabase.table('consumption_records').select('id', count='exact')
        if region:
            count_response = count_response.eq('region', region)
        if month:
            count_response = count_response.eq('month', month)
        if year:
            count_response = count_response.eq('year', year)
        
        total_count = count_response.execute()
        total = total_count.count if hasattr(total_count, 'count') else 0
        
        # Get records - order by id ascending
        response = query.order('id', desc=False).range(offset, offset + limit - 1).execute()
        records = response.data if response.data else []
        
        return jsonify({
            'records': records,
            'total': total
        })
    except Exception as e:
        print(f"Error in api_list_consumption: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Database error: {str(e)}'}), 400

@app.route('/api/consumption/stats-by-region', methods=['GET'])
def api_stats_by_region():
    """Statistics by region."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        year = request.args.get('year', type=int)
        
        stats_by_region = {}
        for region in REGIONS:
            query = supabase.table('consumption_records').select('*').eq('region', region)
            if year:
                query = query.eq('year', year)
            
            response = query.execute()
            region_records = response.data if response.data else []
            
            if region_records:
                stats = calculate_stats(region_records)
                stats['region'] = region
                stats_by_region[region] = stats
        
        return jsonify(list(stats_by_region.values()))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/national-stats', methods=['GET'])
def api_national_stats():
    """National statistics."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        year = request.args.get('year', type=int)
        
        query = supabase.table('consumption_records').select('*')
        if year:
            query = query.eq('year', year)
        
        response = query.execute()
        records = response.data if response.data else []
        stats = calculate_stats(records)
        
        # Count regions with data
        regions_with_data = len(set(r['region'] for r in records))
        
        return jsonify({
            'total_records': stats['count'],
            'regions_count': regions_with_data,
            'total_kwh': stats['total_kwh'],
            'total_bill': stats['total_bill'],
            'avg_kwh': stats['avg_kwh'],
            'avg_bill': stats['avg_bill'],
        })
    except Exception as e:
        print(f"Error in api_national_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Database error: {str(e)}'}), 400

@app.route('/api/consumption/monthly-trends', methods=['GET'])
def api_monthly_trends():
    """Monthly trends."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        region = request.args.get('region')
        
        query = supabase.table('consumption_records').select('*')
        if region:
            query = query.eq('region', region)
        
        response = query.execute()
        records = response.data if response.data else []
        
        # Group by year-month
        trends = {}
        for record in records:
            key = f"{record['year']}-{record['month']:02d}"
            if key not in trends:
                trends[key] = {'year': record['year'], 'month': record['month'], 'region': record['region'], 'kwh_values': [], 'total_kwh': 0, 'count': 0}
            trends[key]['kwh_values'].append(record['kwh'])
            trends[key]['total_kwh'] += record['kwh']
            trends[key]['count'] += 1
        
        result_list = []
        for key in sorted(trends.keys()):
            t = trends[key]
            result_list.append({
                'year': t['year'],
                'month': t['month'],
                'label': f"{MONTHS[t['month']]} {t['year']}",
                'avg_kwh': t['total_kwh'] / t['count'] if t['count'] > 0 else 0,
                'total_kwh': t['total_kwh'],
                'count': t['count'],
            })
        
        return jsonify(result_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/distribution', methods=['GET'])
def api_distribution():
    """Distribution histogram."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        region = request.args.get('region')
        
        query = supabase.table('consumption_records').select('*')
        if region:
            query = query.eq('region', region)
        
        response = query.execute()
        records = response.data if response.data else []
        
        buckets = {
            "0-50": 0,
            "51-110": 0,
            "111-200": 0,
            "201-300": 0,
            "301-500": 0,
            "500+": 0,
        }
        
        for record in records:
            kwh = record['kwh']
            if kwh <= 50:
                buckets["0-50"] += 1
            elif kwh <= 110:
                buckets["51-110"] += 1
            elif kwh <= 200:
                buckets["111-200"] += 1
            elif kwh <= 300:
                buckets["201-300"] += 1
            elif kwh <= 500:
                buckets["301-500"] += 1
            else:
                buckets["500+"] += 1
        
        return jsonify([{'bucket': k, 'count': v} for k, v in buckets.items()])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/region-needs', methods=['GET'])
def api_region_needs():
    """Regional energy needs estimation using multilinear regression.
    
    Estimates energy consumption using regression model: f(region, month, households)
    Sums predictions across 12 months for annual needs per region.
    """
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        year = request.args.get('year', type=int)
        
        query = supabase.table('consumption_records').select('*')
        if year:
            query = query.eq('year', year)
        
        response = query.execute()
        all_records = response.data if response.data else []
        
        if not all_records:
            return jsonify({'error': 'Pas de données disponibles'}), 400
        
        # Estimated households per region
        households_per_region = {
            "Adamaoua": 1300000, "Centre": 4300000, "Est": 100000,
            "Extrême-Nord": 4200000, "Littoral": 3800000, "Nord": 2600000,
            "Nord-Ouest": 1800000, "Ouest": 2300000, "Sud": 870000, "Sud-Ouest": 1200000,
        }
        
        # Train multilinear regression model
        df = pd.DataFrame([{
            'region': r['region'],
            'kwh': r['kwh'],
            'month': r['month'],
            'household_size': r['household_size']
        } for r in all_records])
        
        if len(df) < 3:
            return jsonify({'error': 'Données insuffisantes pour la régression'}), 400
        
        # Create region mapping
        region_mapping = {r: i for i, r in enumerate(sorted(df['region'].unique()))}
        df['region_code'] = df['region'].map(region_mapping)
        
        # Train model: f(region_code, month, household_size) -> kwh
        X = df[['region_code', 'month', 'household_size']].values
        y = df['kwh'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        region_code_coef = model.coef_[0]
        month_coef = model.coef_[1]
        household_coef = model.coef_[2]
        intercept = model.intercept_
        r_squared = model.score(X, y)
        
        # Calculate needs for each region
        result_list = []
        for region in REGIONS:
            if region not in region_mapping:
                continue
            
            households = households_per_region.get(region, 500000)
            region_code = region_mapping[region]
            
            # Sum predictions for all 12 months
            monthly_predictions = []
            for month in range(1, 13):
                # f(region_code, month, households) = intercept + coef_region*region_code + coef_month*month + coef_household*households
                predicted_kwh = intercept + (region_code_coef * region_code) + (month_coef * month) + (household_coef * households)
                monthly_predictions.append(max(0, predicted_kwh))  # Avoid negative predictions
            
            annual_kwh = sum(monthly_predictions)
            avg_monthly_kwh = annual_kwh / 12
            
            # Get sample count for this region
            region_data = df[df['region'] == region]
            sample_count = len(region_data)
            
            result_list.append({
                'region': region,
                'estimated_households': households,
                'estimated_monthly_avg_kwh': round(avg_monthly_kwh, 2),
                'estimated_annual_kwh': round(annual_kwh, 2),
                'estimated_annual_mwh': round(annual_kwh / 1000, 2),
                'estimated_annual_gwh': round(annual_kwh / 1000000, 2),
                'sample_count': sample_count,
                'monthly_breakdown': [round(p, 2) for p in monthly_predictions],
            })
        
        # Sort by annual needs (descending)
        result_list.sort(key=lambda x: x['estimated_annual_gwh'], reverse=True)
        
        return jsonify({
            'metadata': {
                'model_r_squared': round(r_squared, 4),
                'coefficients': {
                    'region': round(region_code_coef, 4),
                    'month': round(month_coef, 4),
                    'household_size': round(household_coef, 4),
                    'intercept': round(intercept, 4)
                },
                'data_points_used': len(df)
            },
            'regions': result_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/export-csv', methods=['GET'])
def api_export_csv():
    """Export data as CSV."""
    try:
        if not supabase:
            return jsonify({'error': 'Base de données non disponible'}), 500
        
        region = request.args.get('region')
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        query = supabase.table('consumption_records').select('*')
        if region:
            query = query.eq('region', region)
        if month:
            query = query.eq('month', month)
        if year:
            query = query.eq('year', year)
        
        response = query.limit(10000).execute()
        records = response.data if response.data else []
        
        # Build CSV
        csv_lines = ["ID,Région,Période,kWh,Facture (FCFA),Ménage,Soumis par,Date"]
        for r in records:
            period = f"{MONTHS[r['month']]} {r['year']}"
            date_str = r['created_at'].split('T')[0] if 'T' in r['created_at'] else r['created_at']
            csv_lines.append(f'{r["id"]},"{r["region"]}","{period}",{r["kwh"]},{int(r["bill_amount"])},{r["household_size"]},"{r["submitter_name"]}","{date_str}"')
        
        csv_content = '\n'.join(csv_lines)
        return jsonify({'csv': csv_content})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ─── Helper function to get all records for ML ────────────────────────────

def get_all_records_for_ml():
    """Get all records as list of dicts for ML functions."""
    if not supabase:
        return []
    
    result = supabase.table('consumption_records').select('*').execute()
    return result.data or []

def get_dataframe_from_records(records=None):
    """Convert consumption records to pandas DataFrame."""
    if records is None:
        records = get_all_records_for_ml()
    
    data = [{
        'region': r['region'],
        'kwh': r['kwh'],
        'month': r['month'],
        'year': r['year'],
        'household_size': r['household_size'],
        'bill_amount': r['bill_amount']
    } for r in records]
    
    return pd.DataFrame(data) if data else pd.DataFrame()
    
    return pd.DataFrame(data)

# ─── Advanced Analysis Functions ──────────────────────────────────────────

def regression_simple():
    """Simple linear regression: consumption vs household size."""
    df = get_dataframe_from_records()
    if len(df) < 2:
        return None
    
    X = df[['household_size']].values
    y = df['kwh'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    r_squared = model.score(X, y)
    
    return {
        'slope': float(model.coef_[0]),
        'intercept': float(model.intercept_),
        'r_squared': float(r_squared),
        'equation': f'kWh = {model.intercept_:.2f} + {model.coef_[0]:.2f} × taille_ménage'
    }

def regression_multiple():
    """Multiple linear regression: consumption vs region, month, household size."""
    df = get_dataframe_from_records()
    if len(df) < 3:
        return None
    
    region_mapping = {r: i for i, r in enumerate(sorted(df['region'].unique()))}
    df['region_code'] = df['region'].map(region_mapping)
    
    X = df[['region_code', 'month', 'household_size']].values
    y = df['kwh'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    r_squared = model.score(X, y)
    
    return {
        'coefficients': {
            'region': float(model.coef_[0]),
            'month': float(model.coef_[1]),
            'household_size': float(model.coef_[2])
        },
        'intercept': float(model.intercept_),
        'r_squared': float(r_squared)
    }

def pca_analysis():
    """Principal Component Analysis for dimensionality reduction."""
    df = get_dataframe_from_records()
    if len(df) < 2:
        return None
    
    region_mapping = {r: i for i, r in enumerate(sorted(df['region'].unique()))}
    df['region_code'] = df['region'].map(region_mapping)
    
    X = df[['region_code', 'month', 'kwh', 'household_size']].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    
    return {
        'explained_variance': [float(v) for v in pca.explained_variance_ratio_],
        'cumulative_variance': float(sum(pca.explained_variance_ratio_)),
        'components': X_pca.tolist()[:50]
    }

def classification_analysis():
    """Classify consumption into categories: Low, Medium, High."""
    df = get_dataframe_from_records()
    if len(df) < 3:
        return None
    
    q1, q3 = df['kwh'].quantile([0.33, 0.67])
    df['category'] = pd.cut(df['kwh'], bins=[0, q1, q3, float('inf')], labels=[0, 1, 2])
    
    region_mapping = {r: i for i, r in enumerate(sorted(df['region'].unique()))}
    df['region_code'] = df['region'].map(region_mapping)
    
    X = df[['region_code', 'month', 'household_size']].values
    y = df['category'].values
    
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    accuracy = model.score(X, y)
    
    return {
        'accuracy': float(accuracy),
        'feature_importance': {
            'region': float(model.feature_importances_[0]),
            'month': float(model.feature_importances_[1]),
            'household_size': float(model.feature_importances_[2])
        },
        'categories': ['Faible', 'Moyen', 'Élevé']
    }

def clustering_analysis():
    """K-means clustering of regions by consumption profile."""
    df = get_dataframe_from_records()
    if len(df) < 3:
        return None
    
    region_stats = df.groupby('region').agg({
        'kwh': ['mean', 'std'],
        'household_size': 'mean'
    }).reset_index()
    
    region_stats.columns = ['region', 'kwh_mean', 'kwh_std', 'household_mean']
    
    X = region_stats[['kwh_mean', 'kwh_std']].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    
    result = []
    for i, region in enumerate(region_stats['region']):
        result.append({
            'region': region,
            'cluster': int(clusters[i]),
            'avg_kwh': float(region_stats.iloc[i]['kwh_mean']),
            'std_kwh': float(region_stats.iloc[i]['kwh_std'])
        })
    
    # Sort clusters by average consumption
    cluster_means = {}
    for item in result:
        cluster_id = item['cluster']
        if cluster_id not in cluster_means:
            cluster_means[cluster_id] = []
        cluster_means[cluster_id].append(item['avg_kwh'])
    
    cluster_avg = {cid: np.mean(values) for cid, values in cluster_means.items()}
    sorted_clusters = sorted(cluster_avg.items(), key=lambda x: x[1])
    cluster_mapping = {old_id: new_id for new_id, (old_id, _) in enumerate(sorted_clusters)}
    
    for item in result:
        item['cluster'] = cluster_mapping[item['cluster']]
    
    # Build regions_by_cluster dictionary
    regions_by_cluster = {}
    for item in result:
        cluster_id = item['cluster']
        if cluster_id not in regions_by_cluster:
            regions_by_cluster[cluster_id] = []
        regions_by_cluster[cluster_id].append(item['region'])
    
    return {
        'clusters': result,
        'n_clusters': 3,
        'regions_by_cluster': regions_by_cluster
    }

def advanced_stats():
    """Calculate advanced descriptive statistics."""
    df = get_dataframe_from_records()
    if len(df) == 0:
        return None
    
    kwh_data = df['kwh'].values
    bill_data = df['bill_amount'].values
    
    return {
        'count': int(len(kwh_data)),
        'total_kwh': float(np.sum(kwh_data)),
        'total_bill': float(np.sum(bill_data)),
        'avg_kwh': float(np.mean(kwh_data)),
        'median_kwh': float(np.median(kwh_data)),
        'std_dev_kwh': float(np.std(kwh_data)),
        'variance': float(np.var(kwh_data)),
        'min_kwh': float(np.min(kwh_data)),
        'max_kwh': float(np.max(kwh_data)),
        'q1': float(np.percentile(kwh_data, 25)),
        'q3': float(np.percentile(kwh_data, 75)),
        'iqr': float(np.percentile(kwh_data, 75) - np.percentile(kwh_data, 25)),
        'skewness': float(stats.skew(kwh_data)),
        'kurtosis': float(stats.kurtosis(kwh_data))
    }

def anova_test():
    """ANOVA test: compare consumption across regions."""
    df = get_dataframe_from_records()
    if len(df) < 2:
        return None
    
    groups = [group['kwh'].values for name, group in df.groupby('region')]
    
    if len(groups) < 2 or any(len(g) == 0 for g in groups):
        return None
    
    try:
        f_stat, p_value = stats.f_oneway(*groups)
    except Exception:
        return None
    
    return {
        'f_statistic': float(f_stat),
        'p_value': float(p_value),
        'significant': p_value < 0.05
    }

def correlation_matrix():
    """Calculate correlation matrix."""
    df = get_dataframe_from_records()
    if len(df) < 2:
        return None
    
    region_mapping = {r: i for i, r in enumerate(sorted(df['region'].unique()))}
    df['region_code'] = df['region'].map(region_mapping)
    
    corr = df[['region_code', 'month', 'kwh', 'household_size']].corr()
    
    return {
        'labels': ['Région', 'Mois', 'kWh', 'Taille ménage'],
        'matrix': corr.values.tolist()
    }

# ─── PDF Generation Function ──────────────────────────────────────────────

def generate_analysis_pdf(analysis_type):
    """Generate comprehensive PDF report for all analyses."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0f1e3d'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a2e52'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title Page
    story.append(Paragraph('Rapport Complet d\'Analyse', title_style))
    story.append(Paragraph('ÉnergieData Cameroun', styles['Normal']))
    story.append(Paragraph('Analyse de la Consommation Électrique', styles['Normal']))
    story.append(Paragraph(f'Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/><br/>', styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # 1. Advanced Statistics
    story.append(Paragraph('1. Statistiques Descriptives Avancées', heading_style))
    data = advanced_stats()
    if data:
        table_data = [['Métrique', 'Valeur']]
        metrics = [
            ('count', 'Nombre d\'observations'),
            ('total_kwh', 'Total kWh'),
            ('avg_kwh', 'Moyenne (kWh)'),
            ('median_kwh', 'Médiane (kWh)'),
            ('min_kwh', 'Min (kWh)'),
            ('max_kwh', 'Max (kWh)'),
            ('std_dev_kwh', 'Écart-type (kWh)'),
            ('skewness', 'Asymétrie'),
            ('kurtosis', 'Aplatissement')
        ]
        for key, label in metrics:
            if key in data:
                value = data[key]
                if isinstance(value, float):
                    table_data.append([label, f'{value:.2f}'])
                else:
                    table_data.append([label, str(value)])
        
        t = Table(table_data, colWidths=[3.5*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f1e3d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4f8')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1'))
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # 2. Simple Linear Regression
    story.append(Paragraph('2. Régression Linéaire Simple', heading_style))
    simple_reg = regression_simple()
    if simple_reg:
        story.append(Paragraph(f'<b>Équation:</b> {simple_reg["equation"]}', styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        table_data = [['Paramètre', 'Valeur', 'Interprétation']]
        table_data.append(['Pente', f'{simple_reg["slope"]:.4f}', 'Variation de consommation par personne'])
        table_data.append(['R²', f'{simple_reg["r_squared"]*100:.2f}%', 'Variance expliquée'])
        
        t = Table(table_data, colWidths=[2*inch, 1.2*inch, 2.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef3c7')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#f59e0b'))
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # 3. Clustering
    story.append(Paragraph('3. Clustering K-means', heading_style))
    clustering = clustering_analysis()
    if clustering and 'n_clusters' in clustering:
        story.append(Paragraph(f'<b>Nombre de clusters:</b> {clustering["n_clusters"]}', styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        for cluster_id, regions in clustering.get('regions_by_cluster', {}).items():
            story.append(Paragraph(f'<b>Cluster {cluster_id}:</b> {", ".join(regions)}', styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ─── Advanced Analysis API Endpoints ──────────────────────────────────────

@app.route('/api/analysis/regression-simple', methods=['GET'])
def api_regression_simple():
    """API endpoint for simple linear regression."""
    try:
        result = regression_simple()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/regression-multiple', methods=['GET'])
def api_regression_multiple():
    """API endpoint for multiple linear regression."""
    try:
        result = regression_multiple()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/pca', methods=['GET'])
def api_pca():
    """API endpoint for PCA analysis."""
    try:
        result = pca_analysis()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/classification', methods=['GET'])
def api_classification():
    """API endpoint for classification analysis."""
    try:
        result = classification_analysis()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/clustering', methods=['GET'])
def api_clustering():
    """API endpoint for K-means clustering."""
    try:
        result = clustering_analysis()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        # Return only the clusters array, not the full dict
        return jsonify(result['clusters'])
    except Exception as e:
        print(f"Clustering error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/advanced-stats', methods=['GET'])
def api_advanced_stats():
    """API endpoint for advanced statistics."""
    try:
        result = advanced_stats()
        if result is None:
            return jsonify({'error': 'Pas de données'}), 400
        # Map the keys to match frontend expectations
        return jsonify({
            'count': result['count'],
            'mean': result['avg_kwh'],
            'median': result['median_kwh'],
            'min': result['min_kwh'],
            'max': result['max_kwh'],
            'std_dev': result['std_dev_kwh'],
            'variance': result['variance'],
            'q1': result['q1'],
            'q3': result['q3'],
            'iqr': result['iqr'],
            'skewness': result['skewness'],
            'kurtosis': result['kurtosis']
        })
    except Exception as e:
        print(f"Advanced stats error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


@app.route('/api/analysis/correlation-matrix', methods=['GET'])
def api_correlation():
    """API endpoint for correlation matrix."""
    try:
        result = correlation_matrix()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/regression-simple')
def page_regression_simple():
    return render_template('regression-simple.html')

@app.route('/advanced-analysis')
def page_advanced_analysis():
    return render_template('advanced-analysis.html')

@app.route('/api/export-pdf/<analysis_type>', methods=['GET'])
def api_export_pdf(analysis_type):
    """Export analysis as PDF."""
    try:
        pdf_buffer = generate_analysis_pdf(analysis_type)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'rapport_{analysis_type.replace(" ", "_").lower()}_{datetime.now().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


# ─── Main ─────────────────────────────────────────────────────────────────

def test_supabase_connection():
    """Test Supabase connection in background"""
    import threading
    import time
    
    def test():
        try:
            time.sleep(1)  # Give Flask time to start
            if supabase:
                response = supabase.table('consumption_records').select('id', count='exact').limit(1).execute()
                print("✅ Supabase connection test passed")
                print(f"📊 Database URL: {SUPABASE_URL[:60]}...")
        except Exception as e:
            print(f"⚠️  Warning: Could not connect to Supabase: {str(e)[:100]}")
    
    thread = threading.Thread(target=test, daemon=True)
    thread.start()

if __name__ == '__main__':
    test_supabase_connection()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
