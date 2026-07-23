from faker import Faker
import random
random.seed(42)
import json
from datetime import timedelta, date

fake = Faker('en_IN')
fake.seed_instance(42)

CRIME_TYPES = ["Theft", "Burglary", "Assault", "Fraud", "Robbery"]
STATIONS = ["MG Road PS", "Whitefield PS", "Koramangala PS"]

# Three tiers of accused persons:
#   - HEAVY repeat offenders: appear in many cases (existing behavior)
#   - MODERATE repeat offenders: appear in a handful of cases (NEW — fills
#     the gap so the risk model has real middle ground to learn from)
#   - everyone else: one-off / first-time cases
HEAVY_REPEAT_OFFENDERS = [fake.name() for _ in range(8)]
MODERATE_REPEAT_OFFENDERS = [fake.name() for _ in range(25)]

def gen_location():
    hotspots = [(12.9716, 77.5946), (12.9352, 77.6146), (12.9698, 77.7500)]
    base_lat, base_lon = random.choice(hotspots)
    return base_lat + random.uniform(-0.02, 0.02), base_lon + random.uniform(-0.02, 0.02)

def pick_accused():
    r = random.random()
    if r < 0.25:
        # 25% chance: heavy repeat offender
        return random.choice(HEAVY_REPEAT_OFFENDERS)
    elif r < 0.45:
        # 20% chance: moderate repeat offender (fills the 2-10 case gap)
        return random.choice(MODERATE_REPEAT_OFFENDERS)
    else:
        # 55% chance: first-time / one-off case
        return fake.name()

def gen_fir(i, day_index):
    lat, lon = gen_location()
    crime = random.choice(CRIME_TYPES)
    d = date(2025, 1, 1) + timedelta(days=day_index)
    accused = pick_accused()
    return {
        "fir_number": f"{i}/2026",
        "police_station": random.choice(STATIONS),
        "date_filed": str(d),
        "crime_type": crime,
        "status": random.choice(["open", "under_investigation", "closed"]),
        "latitude": lat,
        "longitude": lon,
        "accused_name": accused,
        "case_notes": f"On {d}, a {crime.lower()} was reported near {fake.street_name()}. The complainant {fake.name()} stated that {fake.sentence(nb_words=12)}"
    }

TOTAL_DAYS = 365
records = []
i = 1

for day_index in range(TOTAL_DAYS):
    baseline = 1 + int(day_index / 150)
    spike = 6 if 300 <= day_index <= 310 else 0
    n_today = baseline + spike + random.randint(0, 1)

    for _ in range(n_today):
        records.append(gen_fir(i, day_index))
        i += 1

with open("records.json", "w") as f:
    json.dump(records, f, indent=2)

print(f"Generated {len(records)} records into records.json")
print(f"Seeded {len(HEAVY_REPEAT_OFFENDERS)} heavy repeat offenders and {len(MODERATE_REPEAT_OFFENDERS)} moderate repeat offenders")