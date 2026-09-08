"""Static NFL team data.

Extracted from the user's 'Team Info' tab in the original Billy Walters
spreadsheet. Proximity flags mirror the book's proximity factors.
"""

# fields: full_name, conference, division, stadium, city, state,
# lat, lon, dome, turf ("Grass"/"Turf"), tz ("ET"/"CT"/"MT"/"PT"),
# climate ("Warm"/"Cold"), proximity (set of region tags)

TEAMS = {
    "ARI": dict(full_name="Arizona Cardinals", conference="NFC", division="West",
                stadium="State Farm Stadium", city="Glendale", state="AZ",
                lat=33.5275, lon=-112.2625, dome=True, turf="Grass", tz="MT",
                climate="Warm", proximity=set()),
    "ATL": dict(full_name="Atlanta Falcons", conference="NFC", division="South",
                stadium="Mercedes-Benz Stadium", city="Atlanta", state="GA",
                lat=33.755, lon=-84.4008, dome=True, turf="Turf", tz="ET",
                climate="Warm", proximity={"SE"}),
    "BAL": dict(full_name="Baltimore Ravens", conference="AFC", division="North",
                stadium="M&T Bank Stadium", city="Baltimore", state="MD",
                lat=39.278, lon=-76.6227, dome=False, turf="Grass", tz="ET",
                climate="Cold", proximity={"NE", "BAL_WAS"}),
    "BUF": dict(full_name="Buffalo Bills", conference="AFC", division="East",
                stadium="Highmark Stadium", city="Orchard Park", state="NY",
                lat=42.7738, lon=-78.7868, dome=False, turf="Turf", tz="ET",
                climate="Cold", proximity={"NE"}),
    "CAR": dict(full_name="Carolina Panthers", conference="NFC", division="South",
                stadium="Bank of America Stadium", city="Charlotte", state="NC",
                lat=35.2251, lon=-80.8528, dome=False, turf="Grass", tz="ET",
                climate="Warm", proximity={"SE"}),
    "CHI": dict(full_name="Chicago Bears", conference="NFC", division="North",
                stadium="Soldier Field", city="Chicago", state="IL",
                lat=41.8625, lon=-87.6166, dome=False, turf="Grass", tz="CT",
                climate="Cold", proximity={"CHI_GB"}),
    "CIN": dict(full_name="Cincinnati Bengals", conference="AFC", division="North",
                stadium="Paycor Stadium", city="Cincinnati", state="OH",
                lat=39.0954, lon=-84.516, dome=False, turf="Turf", tz="ET",
                climate="Cold", proximity={"IND_CIN"}),
    "CLE": dict(full_name="Cleveland Browns", conference="AFC", division="North",
                stadium="Huntington Bank Field", city="Cleveland", state="OH",
                lat=41.5061, lon=-81.6995, dome=False, turf="Grass", tz="ET",
                climate="Cold", proximity=set()),
    "DAL": dict(full_name="Dallas Cowboys", conference="NFC", division="East",
                stadium="AT&T Stadium", city="Arlington", state="TX",
                lat=32.7473, lon=-97.0945, dome=True, turf="Turf", tz="CT",
                climate="Warm", proximity={"TX"}),
    "DEN": dict(full_name="Denver Broncos", conference="AFC", division="West",
                stadium="Empower Field at Mile High", city="Denver", state="CO",
                lat=39.7439, lon=-105.0201, dome=False, turf="Grass", tz="MT",
                climate="Cold", proximity=set()),
    "DET": dict(full_name="Detroit Lions", conference="NFC", division="North",
                stadium="Ford Field", city="Detroit", state="MI",
                lat=42.34, lon=-83.0456, dome=True, turf="Turf", tz="ET",
                climate="Cold", proximity=set()),
    "GB": dict(full_name="Green Bay Packers", conference="NFC", division="North",
               stadium="Lambeau Field", city="Green Bay", state="WI",
               lat=44.5013, lon=-88.0622, dome=False, turf="Grass", tz="CT",
               climate="Cold", proximity={"CHI_GB"}),
    "HOU": dict(full_name="Houston Texans", conference="AFC", division="South",
                stadium="NRG Stadium", city="Houston", state="TX",
                lat=29.6847, lon=-95.4107, dome=True, turf="Turf", tz="CT",
                climate="Warm", proximity={"TX"}),
    "IND": dict(full_name="Indianapolis Colts", conference="AFC", division="South",
                stadium="Lucas Oil Stadium", city="Indianapolis", state="IN",
                lat=39.7601, lon=-86.1639, dome=True, turf="Turf", tz="ET",
                climate="Cold", proximity={"IND_CIN"}),
    "JAX": dict(full_name="Jacksonville Jaguars", conference="AFC", division="South",
                stadium="EverBank Stadium", city="Jacksonville", state="FL",
                lat=30.3239, lon=-81.6373, dome=False, turf="Grass", tz="ET",
                climate="Warm", proximity={"FL"}),
    "KC": dict(full_name="Kansas City Chiefs", conference="AFC", division="West",
               stadium="Arrowhead Stadium", city="Kansas City", state="MO",
               lat=39.049, lon=-94.4839, dome=False, turf="Grass", tz="CT",
               climate="Cold", proximity=set()),
    "LAC": dict(full_name="Los Angeles Chargers", conference="AFC", division="West",
                stadium="SoFi Stadium", city="Inglewood", state="CA",
                lat=33.9535, lon=-118.3392, dome=True, turf="Turf", tz="PT",
                climate="Warm", proximity={"LA", "LV_LA"}),
    "LAR": dict(full_name="Los Angeles Rams", conference="NFC", division="West",
                stadium="SoFi Stadium", city="Inglewood", state="CA",
                lat=33.9535, lon=-118.3392, dome=True, turf="Turf", tz="PT",
                climate="Warm", proximity={"LA", "LV_LA"}),
    "LV": dict(full_name="Las Vegas Raiders", conference="AFC", division="West",
               stadium="Allegiant Stadium", city="Las Vegas", state="NV",
               lat=36.0908, lon=-115.183, dome=True, turf="Turf", tz="PT",
               climate="Warm", proximity={"LV_LA"}),
    "MIA": dict(full_name="Miami Dolphins", conference="AFC", division="East",
                stadium="Hard Rock Stadium", city="Miami Gardens", state="FL",
                lat=25.958, lon=-80.2389, dome=False, turf="Grass", tz="ET",
                climate="Warm", proximity={"FL"}),
    "MIN": dict(full_name="Minnesota Vikings", conference="NFC", division="North",
                stadium="U.S. Bank Stadium", city="Minneapolis", state="MN",
                lat=44.974, lon=-93.2581, dome=True, turf="Turf", tz="CT",
                climate="Cold", proximity=set()),
    "NE": dict(full_name="New England Patriots", conference="AFC", division="East",
               stadium="Gillette Stadium", city="Foxborough", state="MA",
               lat=42.0909, lon=-71.2643, dome=False, turf="Turf", tz="ET",
               climate="Cold", proximity={"NE"}),
    "NO": dict(full_name="New Orleans Saints", conference="NFC", division="South",
               stadium="Caesars Superdome", city="New Orleans", state="LA",
               lat=29.9511, lon=-90.0812, dome=True, turf="Turf", tz="CT",
               climate="Warm", proximity=set()),
    "NYG": dict(full_name="New York Giants", conference="NFC", division="East",
                stadium="MetLife Stadium", city="East Rutherford", state="NJ",
                lat=40.8135, lon=-74.0745, dome=False, turf="Turf", tz="ET",
                climate="Cold", proximity={"NE", "NYG_NYJ"}),
    "NYJ": dict(full_name="New York Jets", conference="AFC", division="East",
                stadium="MetLife Stadium", city="East Rutherford", state="NJ",
                lat=40.8135, lon=-74.0745, dome=False, turf="Turf", tz="ET",
                climate="Cold", proximity={"NE", "NYG_NYJ"}),
    "PHI": dict(full_name="Philadelphia Eagles", conference="NFC", division="East",
                stadium="Lincoln Financial Field", city="Philadelphia", state="PA",
                lat=39.9008, lon=-75.1675, dome=False, turf="Grass", tz="ET",
                climate="Cold", proximity={"NE"}),
    "PIT": dict(full_name="Pittsburgh Steelers", conference="AFC", division="North",
                stadium="Acrisure Stadium", city="Pittsburgh", state="PA",
                lat=40.4468, lon=-80.0158, dome=False, turf="Grass", tz="ET",
                climate="Cold", proximity=set()),
    "SEA": dict(full_name="Seattle Seahawks", conference="NFC", division="West",
                stadium="Lumen Field", city="Seattle", state="WA",
                lat=47.5952, lon=-122.3316, dome=False, turf="Turf", tz="PT",
                climate="Cold", proximity=set()),
    "SF": dict(full_name="San Francisco 49ers", conference="NFC", division="West",
               stadium="Levi's Stadium", city="Santa Clara", state="CA",
               lat=37.403, lon=-121.97, dome=False, turf="Grass", tz="PT",
               climate="Warm", proximity=set()),
    "TB": dict(full_name="Tampa Bay Buccaneers", conference="NFC", division="South",
               stadium="Raymond James Stadium", city="Tampa", state="FL",
               lat=27.9759, lon=-82.5033, dome=False, turf="Grass", tz="ET",
               climate="Warm", proximity={"FL"}),
    "TEN": dict(full_name="Tennessee Titans", conference="AFC", division="South",
                stadium="Nissan Stadium", city="Nashville", state="TN",
                lat=36.1665, lon=-86.7713, dome=False, turf="Grass", tz="CT",
                climate="Warm", proximity=set()),
    "WSH": dict(full_name="Washington Commanders", conference="NFC", division="East",
                stadium="Northwest Stadium", city="Landover", state="MD",
                lat=38.9078, lon=-76.8644, dome=False, turf="Grass", tz="ET",
                climate="Cold", proximity={"NE", "BAL_WAS"}),
}

# Map various name spellings (ESPN, Massey, Sonny Moore) -> abbreviation
NAME_TO_ABBR = {}
for _abbr, _t in TEAMS.items():
    NAME_TO_ABBR[_t["full_name"].upper()] = _abbr
    NAME_TO_ABBR[_abbr] = _abbr

_EXTRA_ALIASES = {
    "SAN FRANCISCO 49ERS": "SF",
    "WASHINGTON": "WSH", "WAS": "WSH",
    "LA RAMS": "LAR", "LOS ANGELES RAMS": "LAR",
    "LA CHARGERS": "LAC", "LOS ANGELES CHARGERS": "LAC",
    "NY GIANTS": "NYG", "NY JETS": "NYJ",
    "JACKSONVILLE": "JAX", "JAC": "JAX",
    "ARIZONA": "ARI", "ATLANTA": "ATL", "BALTIMORE": "BAL", "BUFFALO": "BUF",
    "CAROLINA": "CAR", "CHICAGO": "CHI", "CINCINNATI": "CIN", "CLEVELAND": "CLE",
    "DALLAS": "DAL", "DENVER": "DEN", "DETROIT": "DET", "GREEN BAY": "GB",
    "HOUSTON": "HOU", "INDIANAPOLIS": "IND", "KANSAS CITY": "KC",
    "LAS VEGAS": "LV", "MIAMI": "MIA", "MINNESOTA": "MIN", "NEW ENGLAND": "NE",
    "NEW ORLEANS": "NO", "PHILADELPHIA": "PHI", "PITTSBURGH": "PIT",
    "SEATTLE": "SEA", "TAMPA BAY": "TB", "TENNESSEE": "TEN",
}
NAME_TO_ABBR.update(_EXTRA_ALIASES)

TZ_OFFSET = {"ET": 0, "CT": -1, "MT": -2, "PT": -3}


def resolve(name: str) -> str | None:
    """Best-effort resolve of any team name string to our abbreviation."""
    if not name:
        return None
    key = name.strip().upper()
    if key in NAME_TO_ABBR:
        return NAME_TO_ABBR[key]
    if len(key) >= 4:  # short codes must match exactly; fuzzy is unsafe
        for full, abbr in NAME_TO_ABBR.items():
            if full in key or key in full:
                return abbr
    return None


# International venues (from the original Team Info tab). ESPN venue names
# are matched loosely against these keys.
INTL_VENUES = {
    "ARENA CORINTHIANS": (-23.5455, -46.4731),      # Sao Paulo
    "CORINTHIANS": (-23.5455, -46.4731),
    "CROKE PARK": (53.3607, -6.251),                # Dublin
    "TOTTENHAM HOTSPUR": (51.6043, -0.0665),        # London
    "WEMBLEY": (51.5559, -0.2796),                  # London
    "OLYMPIASTADION": (52.5147, 13.2396),           # Berlin
    "ALLIANZ ARENA": (48.2188, 11.6247),            # Munich
    "SANTIAGO BERNABEU": (40.4531, -3.6883),        # Madrid
    "BERNABEU": (40.4531, -3.6883),
    "MELBOURNE CRICKET": (-37.8200, 144.9834),      # Melbourne (2026 Wk1)
    "MARACANA": (-22.9122, -43.2302),               # Rio de Janeiro
    "MARACANÃ": (-22.9122, -43.2302),
    "STADE DE FRANCE": (48.9244, 2.3601),           # Paris
    "BAYERN": (48.2188, 11.6247),                   # 'FC Bayern Munich Arena'
    "ESTADIO BANORTE": (19.3029, -99.1505),         # Mexico City (Azteca)
    "AZTECA": (19.3029, -99.1505),
    "BANORTE": (19.3029, -99.1505),
}


def intl_venue_lookup(venue_name: str):
    if not venue_name:
        return None
    import unicodedata
    def norm(s):
        return unicodedata.normalize("NFKD", s).encode(
            "ascii", "ignore").decode().upper()
    key = norm(venue_name.strip())
    for k, latlon in INTL_VENUES.items():
        if norm(k) in key:
            return latlon
    return None
