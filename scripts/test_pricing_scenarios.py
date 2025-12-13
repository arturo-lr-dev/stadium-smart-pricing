
import logging
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pandas as pd

# Add source to path
sys.path.append(".")

from src.core.database import get_db_session
from src.domain.models.match import Match, CompetitionType, MatchStatus
from src.domain.models.zone import Zone, ZoneCategory
from src.domain.services.pricing_engine import PricingEngine
from src.domain.services.demand_predictor import DemandPredictor
from src.domain.services.rules_engine import RulesEngine
from src.domain.services.inventory_manager import InventoryManager
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.ml.models.demand_model import DemandModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_scenarios():
    print("==================================================")
    print("       STADIUM SMART PRICING - SCENARIO TEST      ")
    print("==================================================")

    # 1. Setup Dependencies
    model_path = "models/demand_model.pkl"
    demand_predictor = DemandPredictor(model_path=model_path)
    
    # Mock Repositories
    match_repo = MagicMock(spec=MatchRepository)
    zone_repo = MagicMock(spec=ZoneRepository)
    pricing_repo = MagicMock(spec=PricingHistoryRepository)
    
    # Mock Services that we want to control (Inventory)
    inventory_manager = MagicMock(spec=InventoryManager)
    
    # Real Rules Engine (stateless)
    rules_engine = RulesEngine()
    
    # Create valid objects for testing
    match = Match(
        id="match_test",
        home_team="RCD Mallorca",
        away_team="Real Madrid",
        competition=CompetitionType.LA_LIGA,
        match_date=datetime.now() + timedelta(days=30), # Will be overridden
        status=MatchStatus.SCHEDULED,
        venue="Son Moix",
        capacity=23142,
        is_derby=True
    )
    
    zone = Zone(
        id="zone_test",
        name="Tribuna Oeste",
        category=ZoneCategory.PREMIUM,
        capacity=1000,
        base_price=60.0,
        price_multiplier=1.0,
        min_price=40.0,
        max_price=200.0
    )
    
    # Mock DB Session
    db_session = MagicMock()

    # Initialize Engine
    engine = PricingEngine(
        rules_engine=rules_engine,
        demand_predictor=demand_predictor,
        inventory_manager=inventory_manager,
        match_repository=match_repo,
        zone_repository=zone_repo,
        pricing_repository=pricing_repo,
        db_session=db_session
    )

    # 2. Define Scenarios
    scenarios = []
    
    # Variable: Days to Match
    days_list = [30, 7, 1] 
    # Variable: Weather (via Mocking ExternalFeatureExtractor inside DemandModel if needed, 
    # or just relying on model prediction variations if connected. 
    # NOTE: Since ExternalFeatureExtractor is instantiated INSIDE DemandModel, 
    # we can't easily mock it without patching. 
    # For this script, we will rely on data inputs or patch the methods if strictly needed.
    # To keep it simple and robust, we'll iterate on available inputs first.)
    
    # Variable: Occupancy
    occupancy_list = [10, 50, 90] # %
    
    # Variable: Weather conditions to simulate
    # We will simulate this by patching the method on the instance if possible
    weather_conditions = [
        {"desc": "Sunny/Good", "temp": 25, "rain": 0.0, "wind": 10},
        {"desc": "Rainy/Bad", "temp": 10, "rain": 0.8, "wind": 30}
    ]

    print(f"{'Days':<5} | {'Weather':<12} | {'Occupancy':<10} | {'Base €':<8} | {'Final €':<8} | {'Demand':<10} | {'Mult':<6}")
    print("-" * 75)

    for days in days_list:
        # Update match date
        match.date = datetime.now() + timedelta(days=days)
        
        for occ in occupancy_list:
            # Mock Inventory
            sold = int(zone.capacity * (occ / 100.0))
            inventory_manager.get_zone_inventory.return_value = (sold, zone.capacity - sold)
            
            for weather in weather_conditions:
                # Mock External Features via method patching on the DemandModel instance
                # This is a bit hackerish but effective for scenario testing without full DI injection
                if engine.demand_predictor.model and engine.demand_predictor.model.external_feature_extractor:
                     # Create a mock for the weather extraction method
                    def mock_weather_extract(m):
                        return {
                            "temperature": weather["temp"],
                            "precipitation_probability": weather["rain"],
                            "wind_speed": weather["wind"],
                            "weather_score": 0.2 if weather["desc"] == "Rainy/Bad" else 0.9, # Simplified score
                            "public_transport_available": True,
                            "transport_score": 0.8,
                             "has_competing_event": False
                        }
                    engine.demand_predictor.model.external_feature_extractor.extract_all = mock_weather_extract

                # Calculate Price
                # use a clean date for calculation to match the match.date
                calc_time = datetime.now()
                
                try:
                    price_result = engine._calculate_zone_price(match, zone, calc_time)
                    
                    final_price = price_result.current_price
                    demand_score = price_result.factors.demand_score
                    combined_mult = price_result.factors.calculate_combined_multiplier()
                    
                    print(f"{days:<5} | {weather['desc']:<12} | {occ:<9}% | {zone.base_price:<8} | {final_price:<8.2f} | {demand_score:<10.2f} | {combined_mult:<6.2f}")
                    
                except Exception as e:
                    print(f"Error in scenario (D={days}, W={weather['desc']}, O={occ}%): {e}")

    print("==================================================")
    print("\nFACTOR IMPACT ANALYSIS (Baseline: 7 Days, 50% Occ, Sunny)")
    print(f"{'Factor Tested':<20} | {'Value':<15} | {'Final €':<8} | {'Mult':<6}")
    print("-" * 60)

    # Baseline settings
    base_days = 7
    base_occupancy = 50
    
    # Helper to reset match to baseline
    def get_baseline_match():
        return Match(
            id="match_base",
            home_team="RCD Mallorca",
            away_team="Getafe CF", # Neutral team
            competition=CompetitionType.LA_LIGA,
            match_date=datetime.now() + timedelta(days=base_days),
            status=MatchStatus.SCHEDULED,
            venue="Son Moix",
            capacity=23142,
            is_derby=False
        )
    
    # Define variations
    variations = [
        ("Baseline", {}),
        ("Rival (High)", {"away_team": "Real Madrid"}),
        ("Rival (Low)", {"away_team": "UD Las Palmas"}),
        ("Derby", {"is_derby": True}),
        ("Weekend (Sat)", {"date": datetime.now() + timedelta(days=base_days + (5 - datetime.now().weekday()) % 7)}), # Next Saturday
        ("Weekday (Tue)", {"date": datetime.now() + timedelta(days=base_days + (1 - datetime.now().weekday()) % 7)})  # Next Tuesday
    ]

    for name, changes in variations:
        test_match = get_baseline_match()
        
        # Apply changes
        for attr, val in changes.items():
            setattr(test_match, attr, val)
            
        # Mock Inventory for baseline occupancy
        sold = int(zone.capacity * (base_occupancy / 100.0))
        inventory_manager.get_zone_inventory.return_value = (sold, zone.capacity - sold)
        
        # Calculate
        try:
            price_result = engine._calculate_zone_price(test_match, zone, datetime.now())
            change_val = str(changes.get(list(changes.keys())[0], "Standard")) if changes else "Standard"
            print(f"{name:<20} | {change_val:<15} | {price_result.current_price:<8.2f} | {price_result.factors.calculate_combined_multiplier():<6.2f}")
        except Exception as e:
            print(f"Error in {name}: {e}")

    print("==================================================")

if __name__ == "__main__":
    run_scenarios()
