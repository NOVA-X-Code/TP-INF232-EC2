"""
ÉnergieData Cameroun - Application web python Flask
Plateforme de collecte et d'analyse des données de consommation électrique
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import statistics
from decimal import Decimal
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats
from io import BytesIO
import base64
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime

# ─── Configuration ─────────────────────────────────────────────────────────

app = Flask(__name__)
# Récupération des variables d'environnement (pour Render/Turso)
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
    # Convert libsql:// → sqlite+libsql://
    db_url = TURSO_DATABASE_URL.replace("libsql://", "sqlite+libsql://") + f"?authToken={TURSO_AUTH_TOKEN}"
else:
    db_url = "sqlite:///energie_cameroun.db"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Use SQLite for this Flask app (ignore system DATABASE_URL)
app.config['JSON_SORT_KEYS'] = False

db = SQLAlchemy(app)

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

# ─── Database Models ───────────────────────────────────────────────────────

class ConsumptionRecord(db.Model):
    __tablename__ = 'consumption_records'
    
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(64), nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    kwh = db.Column(db.Float, nullable=False)
    bill_amount = db.Column(db.Float, nullable=False)
    household_size = db.Column(db.Integer, nullable=False)
    submitter_name = db.Column(db.String(255), default="Anonyme")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'region': self.region,
            'month': self.month,
            'month_name': MONTHS.get(self.month, str(self.month)),
            'year': self.year,
            'kwh': self.kwh,
            'bill_amount': self.bill_amount,
            'household_size': self.household_size,
            'submitter_name': self.submitter_name,
            'created_at': self.created_at.isoformat(),
        }

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
    
    kwh_values = [r.kwh for r in records]
    bill_values = [r.bill_amount for r in records]
    
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

@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')

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
            
            # Save to database
            record = ConsumptionRecord(
                region=region,
                month=month,
                year=year,
                kwh=kwh,
                bill_amount=bill_amount,
                household_size=household_size,
                submitter_name=submitter_name or 'Anonyme'
            )
            db.session.add(record)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'id': record.id,
                'bill_amount': bill_amount,
                'message': 'Consommation soumise avec succès!'
            }), 201
        except Exception as e:
            db.session.rollback()
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
        region = request.args.get('region')
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        limit = request.args.get('limit', 500, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = ConsumptionRecord.query
        
        if region:
            query = query.filter_by(region=region)
        if month:
            query = query.filter_by(month=month)
        if year:
            query = query.filter_by(year=year)
        
        total = query.count()
        records = query.order_by(ConsumptionRecord.created_at.desc()).limit(limit).offset(offset).all()
        
        return jsonify({
            'records': [r.to_dict() for r in records],
            'total': total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/stats-by-region', methods=['GET'])
def api_stats_by_region():
    """Statistics by region."""
    try:
        year = request.args.get('year', type=int)
        
        query = ConsumptionRecord.query
        if year:
            query = query.filter_by(year=year)
        
        stats_by_region = {}
        for region in REGIONS:
            region_records = query.filter_by(region=region).all()
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
        year = request.args.get('year', type=int)
        
        query = ConsumptionRecord.query
        if year:
            query = query.filter_by(year=year)
        
        records = query.all()
        stats = calculate_stats(records)
        
        # Count regions with data
        regions_with_data = len(set(r.region for r in records))
        
        return jsonify({
            'total_records': stats['count'],
            'regions_count': regions_with_data,
            'total_kwh': stats['total_kwh'],
            'total_bill': stats['total_bill'],
            'avg_kwh': stats['avg_kwh'],
            'avg_bill': stats['avg_bill'],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/monthly-trends', methods=['GET'])
def api_monthly_trends():
    """Monthly trends."""
    try:
        region = request.args.get('region')
        
        query = ConsumptionRecord.query
        if region:
            query = query.filter_by(region=region)
        
        records = query.all()
        
        # Group by year-month
        trends = {}
        for record in records:
            key = f"{record.year}-{record.month:02d}"
            if key not in trends:
                trends[key] = {'year': record.year, 'month': record.month, 'region': record.region, 'kwh_values': [], 'total_kwh': 0, 'count': 0}
            trends[key]['kwh_values'].append(record.kwh)
            trends[key]['total_kwh'] += record.kwh
            trends[key]['count'] += 1
        
        result = []
        for key in sorted(trends.keys()):
            t = trends[key]
            result.append({
                'year': t['year'],
                'month': t['month'],
                'region': t['region'],
                'label': f"{MONTHS[t['month']]} {t['year']}",
                'avg_kwh': t['total_kwh'] / t['count'] if t['count'] > 0 else 0,
                'total_kwh': t['total_kwh'],
                'count': t['count'],
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/distribution', methods=['GET'])
def api_distribution():
    """Distribution histogram."""
    try:
        region = request.args.get('region')
        
        query = ConsumptionRecord.query
        if region:
            query = query.filter_by(region=region)
        
        records = query.all()
        
        buckets = {
            "0-50": 0,
            "51-110": 0,
            "111-200": 0,
            "201-300": 0,
            "301-500": 0,
            "500+": 0,
        }
        
        for record in records:
            kwh = record.kwh
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
    """Regional energy needs estimation."""
    try:
        year = request.args.get('year', type=int)
        
        query = ConsumptionRecord.query
        if year:
            query = query.filter_by(year=year)
        
        # Estimated households per region (BUCREP approximation)
        households_per_region = {
            "Adamaoua": 450000, "Centre": 1200000, "Est": 380000,
            "Extrême-Nord": 1100000, "Littoral": 850000, "Nord": 620000,
            "Nord-Ouest": 750000, "Ouest": 900000, "Sud": 280000, "Sud-Ouest": 420000,
        }
        
        result = []
        for region in REGIONS:
            region_records = query.filter_by(region=region).all()
            if region_records:
                stats = calculate_stats(region_records)
                households = households_per_region.get(region, 500000)
                monthly_need_mwh = (stats['avg_kwh'] * households) / 1000
                annual_need_gwh = (monthly_need_mwh * 12) / 1000
                
                result.append({
                    'region': region,
                    'avg_monthly_kwh': stats['avg_kwh'],
                    'sample_count': stats['count'],
                    'estimated_households': households,
                    'estimated_monthly_need_mwh': monthly_need_mwh,
                    'estimated_annual_need_gwh': annual_need_gwh,
                })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/consumption/export-csv', methods=['GET'])
def api_export_csv():
    """Export data as CSV."""
    try:
        region = request.args.get('region')
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        query = ConsumptionRecord.query
        if region:
            query = query.filter_by(region=region)
        if month:
            query = query.filter_by(month=month)
        if year:
            query = query.filter_by(year=year)
        
        records = query.limit(10000).all()
        
        # Build CSV
        csv_lines = ["ID,Région,Période,kWh,Facture (FCFA),Ménage,Soumis par,Date"]
        for r in records:
            period = f"{MONTHS[r.month]} {r.year}"
            date = r.created_at.strftime("%Y-%m-%d")
            csv_lines.append(f'{r.id},"{r.region}","{period}",{r.kwh},{int(r.bill_amount)},{r.household_size},"{r.submitter_name}","{date}"')
        
        csv_content = '\n'.join(csv_lines)
        return jsonify({'csv': csv_content})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ─── Advanced Analysis Functions ──────────────────────────────────────────

def get_dataframe_from_records(records=None):
    """Convert consumption records to pandas DataFrame."""
    if records is None:
        records = ConsumptionRecord.query.all()
    
    data = [{
        'region': r.region,
        'kwh': r.kwh,
        'month': r.month,
        'year': r.year,
        'household_size': r.household_size,
        'bill_amount': r.bill_amount
    } for r in records]
    
    return pd.DataFrame(data) if data else pd.DataFrame()

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
    
    # Use only mean and std for clustering (more representative of profile)
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
    
    # Sort clusters by average consumption (low to high) for logical ordering
    cluster_means = {}
    for item in result:
        cluster_id = item['cluster']
        if cluster_id not in cluster_means:
            cluster_means[cluster_id] = []
        cluster_means[cluster_id].append(item['avg_kwh'])
    
    # Calculate mean consumption per cluster
    cluster_avg = {cid: np.mean(values) for cid, values in cluster_means.items()}
    
    # Create mapping: old cluster id -> new sorted cluster id (0=low, 1=medium, 2=high)
    sorted_clusters = sorted(cluster_avg.items(), key=lambda x: x[1])
    cluster_mapping = {old_id: new_id for new_id, (old_id, _) in enumerate(sorted_clusters)}
    
    # Apply mapping to results for logical ordering
    for item in result:
        item['cluster'] = cluster_mapping[item['cluster']]
    
    return result

def advanced_stats():
    """Calculate advanced descriptive statistics."""
    df = get_dataframe_from_records()
    if len(df) == 0:
        return None
    
    kwh_data = df['kwh'].values
    
    return {
        'count': int(len(kwh_data)),
        'mean': float(np.mean(kwh_data)),
        'median': float(np.median(kwh_data)),
        'std_dev': float(np.std(kwh_data)),
        'variance': float(np.var(kwh_data)),
        'min': float(np.min(kwh_data)),
        'max': float(np.max(kwh_data)),
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
    
    # Need at least 2 groups with data
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

# ─── Error Handlers ────────────────────────────────────────────────────────

# ─── PDF Generation Function ────────────────────────────────────────────────────────

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
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=8,
        spaceBefore=8
    )
    
    # Title Page
    story.append(Paragraph('Rapport Complet d\'Analyse', title_style))
    story.append(Paragraph('ÉnergieData Cameroun', styles['Normal']))
    story.append(Paragraph('Analyse de la Consommation Électrique', styles['Normal']))
    story.append(Paragraph(f'Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/><br/>', styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Table of Contents
    story.append(Paragraph('Table des matières', heading_style))
    story.append(Paragraph('1. Statistiques Descriptives Avancées', styles['Normal']))
    story.append(Paragraph('2. Régression Linéaire Simple', styles['Normal']))
    story.append(Paragraph('3. Régression Linéaire Multiple', styles['Normal']))
    story.append(Paragraph('4. Test ANOVA', styles['Normal']))
    story.append(Paragraph('5. Classification Supervisée', styles['Normal']))
    story.append(Paragraph('6. Clustering K-means', styles['Normal']))
    story.append(Paragraph('7. Matrice de Corrélation', styles['Normal']))
    story.append(PageBreak())
    
    # 1. Statistiques Descriptives Avancées
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
                    table_data.append([label, f'{value:.4f}'])
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
    
    # 2. Régression Linéaire Simple
    story.append(Paragraph('2. Régression Linéaire Simple', heading_style))
    story.append(Paragraph('Relation entre la taille du ménage et la consommation électrique', styles['Normal']))
    simple_reg = regression_simple()
    if simple_reg:
        story.append(Paragraph(f'<b>Équation:</b> {simple_reg["equation"]}', styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        table_data = [['Paramètre', 'Valeur', 'Interprétation']]
        table_data.append(['Pente', f'{simple_reg["slope"]:.4f}', 'Variation de consommation par personne (kWh)'])
        table_data.append(['Ordonnée à l\'origine', f'{simple_reg["intercept"]:.2f}', 'Consommation de base estimée (kWh)'])
        table_data.append(['R² (coefficient de détermination)', f'{simple_reg["r_squared"]*100:.2f}%', 'Variance expliquée par le modèle'])
        
        t = Table(table_data, colWidths=[2*inch, 1.2*inch, 2.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef3c7')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#f59e0b'))
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # 3. Régression Linéaire Multiple
    story.append(Paragraph('3. Régression Linéaire Multiple', heading_style))
    story.append(Paragraph('Modèle prédictif : kWh = f(région, mois, taille ménage)', styles['Normal']))
    multi_reg = regression_multiple()
    if multi_reg:
        story.append(Paragraph(f'<b>R² = {multi_reg["r_squared"]*100:.2f}%</b> (Variance expliquée)', styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        table_data = [['Variable', 'Coefficient', 'Interprétation']]
        table_data.append(['Région', f'{multi_reg["coefficients"]["region"]:.4f}', 'Impact de la région'])
        table_data.append(['Mois', f'{multi_reg["coefficients"]["month"]:.4f}', 'Impact du mois/saison'])
        table_data.append(['Taille ménage', f'{multi_reg["coefficients"]["household_size"]:.4f}', 'Impact par personne'])
        table_data.append(['Ordonnée à l\'origine', f'{multi_reg["intercept"]:.2f}', 'Consommation de base'])
        
        t = Table(table_data, colWidths=[2*inch, 1.2*inch, 2.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#dbeafe')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#3b82f6'))
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # 4. Test ANOVA
    story.append(Paragraph('4. Test ANOVA', heading_style))
    story.append(Paragraph('Comparaison de la consommation entre régions (test d\'hypothèse)', styles['Normal']))
    anova = anova_test()
    if anova:
        table_data = [['Métrique', 'Valeur', 'Interprétation']]
        table_data.append(['Statistique F', f'{anova["f_statistic"]:.4f}', 'Ratio variance inter/intra groupes'])
        table_data.append(['P-value', f'{anova["p_value"]:.6f}', 'Probabilité de l\'hypothèse nulle'])
        table_data.append(['Significatif (α=0.05)', 'Oui' if anova['significant'] else 'Non', 'Rejet de H₀' if anova['significant'] else 'Acceptation de H₀'])
        
        interpretation = 'Les différences de consommation entre régions sont statistiquement significatives.' if anova['significant'] else 'Les différences de consommation entre régions ne sont pas statistiquement significatives.'
        
        t = Table(table_data, colWidths=[2*inch, 1.2*inch, 2.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ede9fe')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#8b5cf6'))
        ]))
        story.append(t)
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f'<b>Conclusion:</b> {interpretation}', styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # 5. Classification
    story.append(Paragraph('5. Classification Supervisée', heading_style))
    story.append(Paragraph('Prédiction de catégories de consommation (Faible/Moyen/Élevé)', styles['Normal']))
    classification = classification_analysis()
    if classification and 'accuracy' in classification:
        table_data = [['Métrique', 'Valeur']]
        table_data.append(['Précision (Accuracy)', f'{classification["accuracy"]*100:.2f}%'])
        
        t = Table(table_data, colWidths=[3.5*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d1fae5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#10b981'))
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # 6. Clustering
    story.append(Paragraph('6. Clustering K-means', heading_style))
    story.append(Paragraph('Regroupement des régions par profil énergétique', styles['Normal']))
    clustering = clustering_analysis()
    if clustering and 'n_clusters' in clustering:
        story.append(Paragraph(f'<b>Nombre de clusters identifiés:</b> {clustering["n_clusters"]}', styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        if 'regions_by_cluster' in clustering:
            for cluster_id, regions in clustering['regions_by_cluster'].items():
                story.append(Paragraph(f'<b>Cluster {cluster_id}:</b> {", ".join(regions)}', styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # 7. Matrice de Corrélation
    story.append(Paragraph('7. Matrice de Corrélation', heading_style))
    story.append(Paragraph('Relations entre les variables principales', styles['Normal']))
    corr = correlation_matrix()
    if corr:
        table_data = [[''] + corr['labels']]
        for i, label in enumerate(corr['labels']):
            row = [label]
            for j in range(len(corr['labels'])):
                value = corr['matrix'][i][j]
                row.append(f'{value:.3f}')
            table_data.append(row)
        
        t = Table(table_data, colWidths=[1.2*inch] * (len(corr['labels']) + 1))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (1, 1), (-1, -1), colors.HexColor('#fee2e2')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ef4444'))
        ]))
        story.append(t)
    
    # Build PDF
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
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/advanced-stats', methods=['GET'])
def api_advanced_stats():
    """API endpoint for advanced statistics."""
    try:
        result = advanced_stats()
        if result is None:
            return jsonify({'error': 'Pas de données'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/analysis/anova', methods=['GET'])
def api_anova():
    """API endpoint for ANOVA test."""
    try:
        result = anova_test()
        if result is None:
            return jsonify({'error': 'Pas assez de données'}), 400
        return jsonify(result)
    except Exception as e:
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

if __name__ == '__main__':
    #with app.app_context():
        #db.create_all()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'production')
