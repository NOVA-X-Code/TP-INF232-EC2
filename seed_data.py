"""
Script pour générer et insérer 713 données de test dans la base de données
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

REGION_FACTORS = {
    "Centre": 1.20,
    "Littoral": 1.15,
    "Extrême-Nord": 0.32,
    "Nord": 0.48,
    "Sud-Ouest": 0.74,
    "Ouest": 0.98,
    "Est": 0.80,
    "Nord-Ouest": 0.70,
    "Adamaoua": 0.85,
    "Sud": 0.45,
}

def seed_database():
    """Générer et insérer 713 données de test réalistes"""
    with app.app_context():

        existing_count = ConsumptionRecord.query.count()
        if existing_count > 0:
            print(f"⚠️  La base contient déjà {existing_count} enregistrements.")
            response = input("Continuer et ajouter 713 nouveaux ? (oui/non): ")
            if response.lower() not in ['oui', 'o', 'yes', 'y']:
                print("Annulé.")
                return

        records = []
        start_date = datetime.now() - timedelta(days=365)

        print("🔄 Génération de 713 données de test...")

        for _ in range(713):
            region = random.choice(REGIONS)
            factor = REGION_FACTORS.get(region, 1.0)

            # Taille du ménage (1 à 10)
            household_size = random.randint(1, 10)

            # Base consommation (distribution normale)
            base_kwh = random.gauss(110, 40)

            # Influence région + ménage
            # +10% par personne supplémentaire au-dessus de 1
            household_factor = 1 + (household_size - 1) * 0.10

            kwh = max(15, base_kwh * factor * household_factor)

            month = random.randint(1, 12)
            year = random.choice([2024, 2025, 2026])

            # Tarifs ENEO
            TARIFF_THRESHOLD = 110
            TARIFF_LOW = 50
            TARIFF_HIGH = 79

            if kwh <= TARIFF_THRESHOLD:
                bill_amount = kwh * TARIFF_LOW
            else:
                bill_amount = TARIFF_THRESHOLD * TARIFF_LOW + (kwh - TARIFF_THRESHOLD) * TARIFF_HIGH

            # Date aléatoire
            created_at = start_date + timedelta(days=random.randint(0, 365))

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

        # Insertion par batch
        print("💾 Insertion en base de données...")
        for i in range(0, len(records), 50):
            db.session.add_all(records[i:i+50])
            db.session.commit()
            print(f"  ✓ {i+50 if i+50 < len(records) else len(records)}/713 insérés")

        print("✅ 713 données de test créées avec succès !")

        total = ConsumptionRecord.query.count()
        print(f"\n📊 Statistiques:")
        print(f"  Total enregistrements: {total}")
        print(f"  Régions couvertes: {len(REGIONS)}")

if __name__ == '__main__':
    seed_database()
