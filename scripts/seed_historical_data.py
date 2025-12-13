
import random
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import get_db_session
from src.domain.models.db_models import MatchDB, SaleDB, ZoneDB, MatchStatus, PaymentStatus, CustomerType
from src.domain.models.match import CompetitionType

def seed_history():
    with get_db_session() as db:
        print("Seeding historical data...")
        
        # Get a zone
        zone = db.query(ZoneDB).first()
        if not zone:
            print("No zones found!")
            return

        # Create multiple past matches
        for m_idx in range(5):
            match_date = datetime.now() - timedelta(days=30 * (m_idx + 1))
            past_match = MatchDB(
                id=f"match_past_{m_idx}",
                home_team="RCD Mallorca",
                away_team=f"Opponent {m_idx}",
                competition=CompetitionType.LA_LIGA.value,
                match_date=match_date,
                status=MatchStatus.COMPLETED,
                venue="Son Moix",
                capacity=23142,
                is_derby=random.choice([True, False])
            )
            db.merge(past_match)
            
            # Create sales for this match
            for i in range(50):
                sale = SaleDB(
                    id=f"sale_past_{m_idx}_{i}",
                    match_id=past_match.id,
                    zone_id=zone.id,
                    quantity=random.randint(1, 4),
                    price_per_ticket=50.0,
                    total_amount=50.0,
                    customer_type=CustomerType.GENERAL,
                    payment_status=PaymentStatus.COMPLETED,
                    purchase_datetime=match_date - timedelta(days=random.randint(1, 20))
                )
                sale.total_amount = sale.quantity * sale.price_per_ticket
                db.merge(sale)
            
        db.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_history()
