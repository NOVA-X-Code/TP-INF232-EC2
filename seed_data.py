"""
Script pour générer et insérer 256 données de test dans la base de données
"""

import random
from datetime import datetime, timedelta
from app import app, db, ConsumptionRecord

REGIONS = [
    "Adamaoua", "Centre", "Est", "Extrême-Nord", "Littoral",
    "Nord", "Nord-Ouest", "Ouest", "Sud", "Sud-Ouest"
]

NAMES = [
    "Anonyme", "Jean Dupont", "Marie Martin", "Pierre Bernard", "Sophie Garcia",
    "Luc Fontaine", "Emma Mercier", "Claude Rousseau", "Isabelle Lefevre", "Michel Durand",
    "Anne Leblanc", "Nicolas Garnier", "Stephanie Vincent", "Thomas Dufour", "Catherine Moreau",
    "Benjamin Leroy", "Florence Mathieu", "Julien Girard", "Valerie Blanchard", "Marc Leduc",
]

def seed_database():
    """Générer et insérer 256 données de test"""
    with app.app_context():
        # Vérifier si la BD a déjà des données
        existing_count = ConsumptionRecord.query.count()
        if existing_count > 0:
            print(f"⚠️  La base contient déjà {existing_count} enregistrements.")
            response = input("Continuer et ajouter 256 nouveaux ? (oui/non): ")
            if response.lower() not in ['oui', 'o', 'yes', 'y']:
                print("Annulé.")
                return
        
        records = []
        start_date = datetime.now() - timedelta(days=365)
        
        print("🔄 Génération de 256 données de test...")
        
        for i in range(311):
            region = random.choice(REGIONS)
            
            # Varier la consommation par région (données réalistes)
            region_factors = {
                "Centre": 1.2,
                "Littoral": 1.15,
                "Extrême-Nord": 0.3,
                "Nord": 0.48,
                "Sud-Ouest": 0.74,
                "Ouest": 0.95,
                "Est": 0.8,
                "Nord-Ouest": 0.7,
                "Adamaoua": 0.85,
                "Sud": 0.45,
            }
            
            factor = region_factors.get(region, 1.0)
            base_kwh = random.gauss(120, 50)  # Distribution normale centrée à 120 kWh
            kwh = max(20, base_kwh * factor)  # Min 20 kWh
            
            month = random.randint(1, 12)
            year = random.choice([2024, 2025, 2026])
            household_size = random.randint(1, 10)
            
            # Calculer la facture (tarif ENEO)
            TARIFF_THRESHOLD = 110
            TARIFF_LOW = 50
            TARIFF_HIGH = 79
            
            if kwh <= TARIFF_THRESHOLD:
                bill_amount = kwh * TARIFF_LOW
            else:
                bill_amount = TARIFF_THRESHOLD * TARIFF_LOW + (kwh - TARIFF_THRESHOLD) * TARIFF_HIGH
            
            # Date aléatoire dans l'année
            random_days = random.randint(0, 365)
            created_at = start_date + timedelta(days=random_days)
            
            record = ConsumptionRecord(
                region=region,
                month=month,
                year=year,
                kwh=round(kwh, 2),
                bill_amount=round(bill_amount, 0),
                household_size=household_size,
                submitter_name=random.choice(NAMES),
                created_at=created_at
            )
            records.append(record)
        
        # Insérer par batch de 50 pour plus de performance
        print("💾 Insertion en base de données...")
        for i in range(0, len(records), 50):
            batch = records[i:i+50]
            db.session.add_all(batch)
            db.session.commit()
            print(f"  ✓ {i+len(batch)}/256 enregistrements insérés")
        
        print("✅ 256 données de test créées avec succès!")
        
        # Afficher les statistiques
        total = ConsumptionRecord.query.count()
        print(f"\n📊 Statistiques:")
        print(f"  Total enregistrements: {total}")
        print(f"  Régions couvertes: {len(REGIONS)}")

if __name__ == '__main__':
    seed_database()
