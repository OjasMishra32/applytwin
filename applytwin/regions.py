"""International support: countries, cities and regions; where a posting is; the user's target countries and work rights
in each; program names that differ by country (placement year, Werkstudent, graduate scheme, campus hiring, PPO); the
application questions forms ask outside the US; and local resume conventions (CV, A4, CGPA out of 10).

Everything here is plain data and small functions, so match.py, answers.py, sources.py and tailor.py each call in with
one line. Never invents a fact: a value the user hasn't given comes back blank, and the agent asks.
"""
import functools
import re
import unicodedata

# ------------------------------------------------------------------ countries and cities
# code: (name, other names (lowercase, accent-free), ISO3, region, cities {canonical: [aliases]}, currency, dial code)
C = {
    'US': ('United States', ['united states', 'united states of america', 'usa', 'u.s.', 'u.s.a.', 'america'], 'USA', 'americas',
           {}, 'USD', '+1'),
    'CA': ('Canada', ['canada'], 'CAN', 'americas',
           {'Toronto': ['toronto'], 'Vancouver': ['vancouver'], 'Montreal': ['montreal'], 'Ottawa': ['ottawa'], 'Waterloo': ['waterloo', 'kitchener'],
            'Calgary': ['calgary'], 'Edmonton': ['edmonton'], 'Mississauga': ['mississauga']}, 'CAD', '+1'),
    'GB': ('United Kingdom', ['united kingdom', 'uk', 'u.k.', 'great britain', 'britain', 'england', 'scotland', 'wales', 'northern ireland'],
           'GBR', 'europe',
           {'London': ['london', 'city of london', 'canary wharf', 'greater london'], 'Manchester': ['manchester'], 'Edinburgh': ['edinburgh'],
            'Glasgow': ['glasgow'], 'Cambridge': ['cambridge'], 'Oxford': ['oxford'], 'Bristol': ['bristol'], 'Birmingham': ['birmingham'],
            'Leeds': ['leeds'], 'Belfast': ['belfast'], 'Cardiff': ['cardiff'], 'Reading': ['reading'], 'Newcastle': ['newcastle'],
            'Sheffield': ['sheffield'], 'Nottingham': ['nottingham'], 'Brighton': ['brighton'], 'Guildford': ['guildford'],
            'Southampton': ['southampton'], 'Liverpool': ['liverpool'], 'Milton Keynes': ['milton keynes'], 'Slough': ['slough']}, 'GBP', '+44'),
    'IE': ('Ireland', ['ireland', 'republic of ireland'], 'IRL', 'europe',
           {'Dublin': ['dublin'], 'Cork': ['cork'], 'Galway': ['galway'], 'Limerick': ['limerick']}, 'EUR', '+353'),
    'DE': ('Germany', ['germany', 'deutschland'], 'DEU', 'europe',
           {'Berlin': ['berlin'], 'Munich': ['munich', 'munchen', 'muenchen', 'garching', 'ottobrunn', 'unterfohring'], 'Hamburg': ['hamburg'],
            'Frankfurt': ['frankfurt', 'frankfurt am main', 'frankfurt a. m.', 'frankfurt a.m.'], 'Cologne': ['cologne', 'koln', 'koeln'],
            'Stuttgart': ['stuttgart'], 'Dusseldorf': ['dusseldorf', 'duesseldorf'], 'Leipzig': ['leipzig'], 'Dresden': ['dresden'],
            'Karlsruhe': ['karlsruhe'], 'Heidelberg': ['heidelberg'], 'Nuremberg': ['nuremberg', 'nurnberg', 'nuernberg'],
            'Hannover': ['hannover', 'hanover'], 'Aachen': ['aachen'], 'Darmstadt': ['darmstadt'], 'Walldorf': ['walldorf'],
            'Erlangen': ['erlangen'], 'Bonn': ['bonn'], 'Wolfsburg': ['wolfsburg'], 'Ingolstadt': ['ingolstadt']}, 'EUR', '+49'),
    'NL': ('Netherlands', ['netherlands', 'the netherlands', 'holland', 'nederland'], 'NLD', 'europe',
           {'Amsterdam': ['amsterdam', 'amstelveen', 'hoofddorp'], 'Rotterdam': ['rotterdam'], 'The Hague': ['the hague', 'den haag', "'s-gravenhage"],
            'Utrecht': ['utrecht'], 'Eindhoven': ['eindhoven', 'veldhoven'], 'Delft': ['delft'], 'Leiden': ['leiden'], 'Groningen': ['groningen']},
           'EUR', '+31'),
    'FR': ('France', ['france'], 'FRA', 'europe',
           {'Paris': ['paris', 'ile-de-france', 'ile de france', 'la defense', 'idf'], 'Lyon': ['lyon'], 'Toulouse': ['toulouse'],
            'Marseille': ['marseille'], 'Nice': ['nice', 'sophia antipolis'], 'Bordeaux': ['bordeaux'], 'Lille': ['lille'], 'Nantes': ['nantes'],
            'Grenoble': ['grenoble'], 'Montpellier': ['montpellier'], 'Rennes': ['rennes']}, 'EUR', '+33'),
    'CH': ('Switzerland', ['switzerland', 'schweiz', 'suisse'], 'CHE', 'europe',
           {'Zurich': ['zurich', 'zuerich'], 'Geneva': ['geneva', 'geneve', 'genf'], 'Basel': ['basel'], 'Lausanne': ['lausanne'],
            'Bern': ['bern'], 'Zug': ['zug'], 'Lugano': ['lugano'], 'Rotkreuz': ['rotkreuz']}, 'CHF', '+41'),
    'SE': ('Sweden', ['sweden', 'sverige'], 'SWE', 'europe',
           {'Stockholm': ['stockholm'], 'Gothenburg': ['gothenburg', 'goteborg'], 'Malmo': ['malmo'], 'Lund': ['lund'], 'Uppsala': ['uppsala'],
            'Linkoping': ['linkoping']}, 'SEK', '+46'),
    'NO': ('Norway', ['norway', 'norge'], 'NOR', 'europe',
           {'Oslo': ['oslo'], 'Bergen': ['bergen'], 'Trondheim': ['trondheim'], 'Stavanger': ['stavanger']}, 'NOK', '+47'),
    'DK': ('Denmark', ['denmark', 'danmark'], 'DNK', 'europe',
           {'Copenhagen': ['copenhagen', 'kobenhavn', 'soborg'], 'Aarhus': ['aarhus'], 'Odense': ['odense'], 'Aalborg': ['aalborg']}, 'DKK', '+45'),
    'FI': ('Finland', ['finland', 'suomi'], 'FIN', 'europe',
           {'Helsinki': ['helsinki', 'espoo', 'vantaa'], 'Tampere': ['tampere'], 'Oulu': ['oulu'], 'Turku': ['turku']}, 'EUR', '+358'),
    'IS': ('Iceland', ['iceland'], 'ISL', 'europe', {'Reykjavik': ['reykjavik']}, 'ISK', '+354'),
    'ES': ('Spain', ['spain', 'espana'], 'ESP', 'europe',
           {'Madrid': ['madrid'], 'Barcelona': ['barcelona', 'sant cugat'], 'Valencia': ['valencia'], 'Seville': ['seville', 'sevilla'],
            'Malaga': ['malaga'], 'Bilbao': ['bilbao']}, 'EUR', '+34'),
    'PT': ('Portugal', ['portugal'], 'PRT', 'europe', {'Lisbon': ['lisbon', 'lisboa'], 'Porto': ['porto'], 'Braga': ['braga']}, 'EUR', '+351'),
    'IT': ('Italy', ['italy', 'italia'], 'ITA', 'europe',
           {'Milan': ['milan', 'milano'], 'Rome': ['rome', 'roma'], 'Turin': ['turin', 'torino'], 'Bologna': ['bologna']}, 'EUR', '+39'),
    'BE': ('Belgium', ['belgium', 'belgique', 'belgie'], 'BEL', 'europe',
           {'Brussels': ['brussels', 'bruxelles', 'brussel'], 'Antwerp': ['antwerp', 'antwerpen'], 'Ghent': ['ghent', 'gent'], 'Leuven': ['leuven']},
           'EUR', '+32'),
    'AT': ('Austria', ['austria', 'osterreich'], 'AUT', 'europe', {'Vienna': ['vienna', 'wien'], 'Graz': ['graz'], 'Linz': ['linz']}, 'EUR', '+43'),
    'LU': ('Luxembourg', ['luxembourg'], 'LUX', 'europe', {'Luxembourg City': ['luxembourg city']}, 'EUR', '+352'),
    'PL': ('Poland', ['poland', 'polska'], 'POL', 'europe',
           {'Warsaw': ['warsaw', 'warszawa'], 'Krakow': ['krakow', 'cracow'], 'Wroclaw': ['wroclaw'], 'Gdansk': ['gdansk', 'gdynia', 'sopot'],
            'Poznan': ['poznan'], 'Lodz': ['lodz'], 'Katowice': ['katowice']}, 'PLN', '+48'),
    'CZ': ('Czechia', ['czechia', 'czech republic'], 'CZE', 'europe', {'Prague': ['prague', 'praha'], 'Brno': ['brno']}, 'CZK', '+420'),
    'RO': ('Romania', ['romania'], 'ROU', 'europe', {'Bucharest': ['bucharest', 'bucuresti'], 'Cluj': ['cluj', 'cluj-napoca'], 'Iasi': ['iasi']},
           'RON', '+40'),
    'HU': ('Hungary', ['hungary'], 'HUN', 'europe', {'Budapest': ['budapest']}, 'HUF', '+36'),
    'GR': ('Greece', ['greece'], 'GRC', 'europe', {'Athens': ['athens']}, 'EUR', '+30'),
    'EE': ('Estonia', ['estonia'], 'EST', 'europe', {'Tallinn': ['tallinn']}, 'EUR', '+372'),
    'LT': ('Lithuania', ['lithuania'], 'LTU', 'europe', {'Vilnius': ['vilnius']}, 'EUR', '+370'),
    'LV': ('Latvia', ['latvia'], 'LVA', 'europe', {'Riga': ['riga']}, 'EUR', '+371'),
    'IN': ('India', ['india', 'bharat'], 'IND', 'apac',
           {'Bengaluru': ['bengaluru', 'bangalore', 'banglore', 'banagalore', 'blr'], 'Hyderabad': ['hyderabad', 'secunderabad'],
            'Pune': ['pune'], 'Delhi NCR': ['delhi ncr', 'new delhi', 'delhi', 'ncr', 'gurgaon', 'gurugram', 'noida', 'greater noida',
                                            'ghaziabad', 'faridabad'],
            'Mumbai': ['mumbai', 'bombay', 'navi mumbai', 'thane', 'powai'], 'Chennai': ['chennai', 'madras'], 'Kolkata': ['kolkata', 'calcutta'],
            'Ahmedabad': ['ahmedabad', 'gandhinagar', 'gift city'], 'Jaipur': ['jaipur'], 'Kochi': ['kochi', 'cochin'],
            'Coimbatore': ['coimbatore'], 'Indore': ['indore'], 'Chandigarh': ['chandigarh', 'mohali'],
            'Thiruvananthapuram': ['thiruvananthapuram', 'trivandrum'], 'Mysuru': ['mysuru', 'mysore']}, 'INR', '+91'),
    'SG': ('Singapore', ['singapore'], 'SGP', 'apac', {'Singapore': ['singapore']}, 'SGD', '+65'),
    'AE': ('United Arab Emirates', ['united arab emirates', 'uae', 'u.a.e.'], 'ARE', 'emea', {'Dubai': ['dubai'], 'Abu Dhabi': ['abu dhabi']},
           'AED', '+971'),
    'AU': ('Australia', ['australia'], 'AUS', 'apac',
           {'Sydney': ['sydney'], 'Melbourne': ['melbourne'], 'Brisbane': ['brisbane'], 'Perth': ['perth'], 'Canberra': ['canberra'],
            'Adelaide': ['adelaide']}, 'AUD', '+61'),
    'NZ': ('New Zealand', ['new zealand'], 'NZL', 'apac', {'Auckland': ['auckland'], 'Wellington': ['wellington']}, 'NZD', '+64'),
    'HK': ('Hong Kong', ['hong kong', 'hong kong sar'], 'HKG', 'apac', {'Hong Kong': ['hong kong', 'kowloon']}, 'HKD', '+852'),
    'JP': ('Japan', ['japan'], 'JPN', 'apac', {'Tokyo': ['tokyo'], 'Osaka': ['osaka']}, 'JPY', '+81'),
    'IL': ('Israel', ['israel'], 'ISR', 'emea', {'Tel Aviv': ['tel aviv', 'tel-aviv', 'herzliya'], 'Haifa': ['haifa'], 'Jerusalem': ['jerusalem']},
           'ILS', '+972'),
}
for _k, (_n, _al, _i3, _cities) in {   # elsewhere: named so a posting there reads as "outside your countries (Vietnam)"
    'CN': ('China', ['china', 'prc'], 'CHN', ['shanghai', 'beijing', 'shenzhen', 'guangzhou', 'hangzhou', 'chengdu', 'suzhou', 'nanjing', 'xi\'an', 'tianjin', 'dalian', 'wuhan']),
    'TW': ('Taiwan', ['taiwan'], 'TWN', ['taipei', 'hsinchu', 'taichung', 'kaohsiung']),
    'KR': ('South Korea', ['south korea', 'korea'], 'KOR', ['seoul', 'busan']),
    'VN': ('Vietnam', ['vietnam', 'viet nam'], 'VNM', ['ho chi minh', 'ho chi minh city', 'hcmc', 'hanoi', 'da nang']),
    'PH': ('Philippines', ['philippines'], 'PHL', ['manila', 'taguig', 'makati', 'cebu', 'pasig', 'quezon city']),
    'ID': ('Indonesia', ['indonesia'], 'IDN', ['jakarta', 'bali', 'surabaya', 'bandung']),
    'MY': ('Malaysia', ['malaysia'], 'MYS', ['kuala lumpur', 'penang', 'kulim', 'cyberjaya']),
    'TH': ('Thailand', ['thailand'], 'THA', ['bangkok', 'chon buri']),
    'BR': ('Brazil', ['brazil', 'brasil'], 'BRA', ['sao paulo', 'rio de janeiro', 'curitiba', 'belo horizonte', 'porto alegre']),
    'MX': ('Mexico', ['mexico'], 'MEX', ['mexico city', 'guadalajara', 'monterrey', 'ciudad de mexico']),
    'AR': ('Argentina', ['argentina'], 'ARG', ['buenos aires', 'cordoba']),
    'CO': ('Colombia', ['colombia'], 'COL', ['bogota', 'medellin']),
    'CL': ('Chile', ['chile'], 'CHL', ['santiago']),
    'PE': ('Peru', ['peru'], 'PER', ['lima']),
    'TR': ('Turkey', ['turkey', 'turkiye'], 'TUR', ['istanbul', 'ankara']),
    'EG': ('Egypt', ['egypt'], 'EGY', ['cairo']),
    'ZA': ('South Africa', ['south africa'], 'ZAF', ['johannesburg', 'cape town']),
    'NG': ('Nigeria', ['nigeria'], 'NGA', ['lagos']),
    'KE': ('Kenya', ['kenya'], 'KEN', ['nairobi']),
    'PK': ('Pakistan', ['pakistan'], 'PAK', ['karachi', 'lahore', 'islamabad']),
    'BD': ('Bangladesh', ['bangladesh'], 'BGD', ['dhaka']),
    'LK': ('Sri Lanka', ['sri lanka'], 'LKA', ['colombo']),
    'SA': ('Saudi Arabia', ['saudi arabia', 'ksa'], 'SAU', ['riyadh', 'jeddah']),
    'QA': ('Qatar', ['qatar'], 'QAT', ['doha']),
    'JO': ('Jordan', ['jordan'], 'JOR', ['amman']),
    'MA': ('Morocco', ['morocco'], 'MAR', ['casablanca', 'rabat']),
    'UA': ('Ukraine', ['ukraine'], 'UKR', ['kyiv', 'kiev', 'lviv']),
    'RS': ('Serbia', ['serbia'], 'SRB', ['belgrade', 'novi sad']),
    'HR': ('Croatia', ['croatia'], 'HRV', ['zagreb']),
    'BG': ('Bulgaria', ['bulgaria'], 'BGR', ['sofia']),
    'SK': ('Slovakia', ['slovakia'], 'SVK', ['bratislava']),
    'SI': ('Slovenia', ['slovenia'], 'SVN', ['ljubljana']),
    'CY': ('Cyprus', ['cyprus'], 'CYP', ['limassol', 'nicosia']),
    'MT': ('Malta', ['malta'], 'MLT', ['valletta']),
    'KZ': ('Kazakhstan', ['kazakhstan'], 'KAZ', ['almaty', 'astana']),
    'MK': ('North Macedonia', ['north macedonia', 'macedonia'], 'MKD', ['skopje']),
}.items():
    C[_k] = (_n, _al, _i3, 'other', {_c.title(): [_c] for _c in _cities}, '', '')
NAMES = {k: v[0] for k, v in C.items()}
CURRENCY = {k: v[5] for k, v in C.items()}
DIAL = {k: v[6] for k, v in C.items()}
ISO3 = {v[2]: k for k, v in C.items()}
EEA = {'IE', 'DE', 'NL', 'FR', 'SE', 'NO', 'DK', 'FI', 'IS', 'ES', 'PT', 'IT', 'BE', 'AT', 'LU', 'PL', 'CZ', 'RO', 'HU', 'GR', 'EE', 'LT', 'LV',
       'CH'}   # free movement for EU/EEA citizens (Switzerland by treaty); the UK left in 2021
EEA |= {'HR', 'BG', 'SK', 'SI', 'CY', 'MT'}
EUROPE = EEA | {'GB'}
GROUPS = {   # words postings use for a whole area, and the countries each covers
    'europe': EUROPE, 'eu': EEA, 'eea': EEA, 'emea': EUROPE | {'AE', 'IL'}, 'dach': {'DE', 'AT', 'CH'}, 'nordics': {'SE', 'NO', 'DK', 'FI', 'IS'},
    'benelux': {'BE', 'NL', 'LU'}, 'apac': {'IN', 'SG', 'AU', 'NZ', 'HK', 'JP'}, 'asia': {'IN', 'SG', 'HK', 'JP'},
    'americas': {'US', 'CA'}, 'north america': {'US', 'CA'}, 'middle east': {'AE', 'IL'}, 'gcc': {'AE'},
}
GLOBAL = re.compile(r'\b(anywhere|worldwide|global(ly)?|international|any location|all locations)\b', re.I)
REMOTE = re.compile(r'\b(remote|home[- ]based|work from home|wfh|distributed|telecommute)\b', re.I)
HYBRID = re.compile(r'\bhybrid\b', re.I)
CA_PROV = re.compile(r',\s*(ON|BC|QC|AB|MB|NS|NB|NL|PE|SK)\b(?!\s*,\s*(?:US|USA)\b)')
STATES = set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC '
             'SD TN TX UT VT VA WA WV WI WY DC'.split())
US_CITY = re.compile(r'\b(new york|nyc|san francisco|bay area|seattle|boston|chicago|austin|los angeles|atlanta|denver|mountain view|'
                     r'palo alto|sunnyvale|menlo park|san jose|redmond|bellevue|pittsburgh|philadelphia|miami|houston|dallas|'
                     r'washington,? d\.?c\.?|arlington|san diego|salt lake city|raleigh|charlotte|nashville|minneapolis|detroit|portland|phoenix)\b', re.I)


US_STATE_NAME = re.compile(r'(?:,|-)\s*(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|'
                           r'idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|'
                           r'mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|'
                           r'north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|'
                           r'utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b(?!\s*,\s*(?!united states|usa)[a-z])')


def fold(s):
    """'München' -> 'munchen', 'Kraków' -> 'krakow': compare without accents."""
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).replace('ł', 'l').replace('Ł', 'L').replace('ø', 'o').replace('æ', 'ae')


def _alias_re(words):
    words = sorted(set(words), key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + '|'.join(re.escape(w) for w in words) + r")(?!\w)", re.I)


_COUNTRY_RE = {k: _alias_re(v[1] + [v[0].lower()]) for k, v in C.items()}
_ALIAS_CODE = {}
for _k, _v in C.items():
    if _k != 'US':
        for _a in _v[1] + [_v[0].lower()]:
            _ALIAS_CODE.setdefault(_a, _k)
_ANY_COUNTRY = _alias_re(list(_ALIAS_CODE))   # one pass over the text instead of one regex per country
_CITY = {}   # alias -> (code, canonical)
for _k, _v in C.items():
    for _canon, _al in _v[4].items():
        for _a in _al + [_canon.lower()]:
            _CITY.setdefault(_a, (_k, _canon))
_CITY_RE = _alias_re(list(_CITY))
_GROUP_RE = re.compile(r'(?<![\w-])(europe|european union|emea|eea|dach|nordics?|benelux|apac|asia[- ]pacific|asia|americas|north america|'
                       r'middle east|gcc)(?![\w-])', re.I)
_EU_WORD = re.compile(r'(?<![\w-])EU(?![\w-])')   # "EU Remote" (uppercase only: never the letters in a word)


def _group_key(w):
    w = w.lower()
    return {'european union': 'eu', 'nordic': 'nordics', 'asia-pacific': 'apac', 'asia pacific': 'apac'}.get(w, w)


def _segments(loc):
    loc = re.sub(r'[\U0001F1E6-\U0001F1FF]', ' ', loc or '')    # flag emoji
    parts = re.split(r';|\||\n|\s+/\s+|\s+or\s+|\s+and\s+|\s+&\s+|•|\s+-\s+(?=remote\b)', loc, flags=re.I)
    out = []
    for p in parts:
        p = p.strip(' ,-–()[]')
        if p:
            out.append(p)
    return out


def parse_one(seg):
    """One place -> {'country', 'city', 'group', 'remote', 'hybrid', 'raw'}; any of them None/False when the text doesn't say."""
    raw = seg
    f = fold(seg)
    low = f.lower()
    r = {'country': None, 'city': None, 'group': None, 'remote': bool(REMOTE.search(f)), 'hybrid': bool(HYBRID.search(f)), 'raw': raw}
    if re.fullmatch(r'\s*\d+\s+locations?\s*', low):
        return r
    # 1. country words ("India", "United Kingdom", "Deutschland") and ISO3 codes ("IND", "GBR", "Bengaluru, IND")
    m = _ANY_COUNTRY.search(low)
    if m:
        r['country'] = _ALIAS_CODE.get(m.group(1).lower())
    if not r['country']:
        m = re.search(r'(?<![A-Za-z])(%s)(?![A-Za-z])' % '|'.join(c for c in ISO3 if c != 'USA'), f)
        if m:
            r['country'] = ISO3[m.group(1)]
    # 2. two-letter codes: a prefix ("UK London", "IN-KA-Bengaluru", "AE - Abu Dhabi", "GB-London") or a suffix after a comma
    #    ("Madrid, ES"). A suffix that is also a US state ("Berlin, DE" vs "Dover, DE") goes by the city.
    city_hit = _CITY_RE.search(low)
    city = _CITY.get(city_hit.group(1).lower()) if city_hit else None
    if not r['country']:
        m = re.match(r'\s*([A-Z]{2})(?:\s*[-–:]\s*|\s+)(?=[A-Z])', seg)
        code = m.group(1) if m else None
        code = 'GB' if code == 'UK' else code
        if code in C and code != 'US' and not (code == 'CA' and re.match(r'\s*CA\s*[-–]?\s*(San|Los|Santa|Palo|Mountain|Sunnyvale)', seg)):
            r['country'] = code
        else:
            m = re.search(r',\s*([A-Z]{2})\s*$', seg)
            if m:
                code = 'GB' if m.group(1) == 'UK' else m.group(1)
                if CA_PROV.search(seg):
                    r['country'] = 'CA'
                elif city and city[0] == code:
                    r['country'] = code
                elif code in STATES:
                    r['country'] = 'US'
                elif code in C:
                    r['country'] = code
    # 3. a Canadian province or a US state beats a city name that exists in both places ("London, ON", "Cambridge, MA")
    if not r['country']:
        if CA_PROV.search(seg):
            r['country'] = 'CA'
        elif re.search(r'\b(united states|usa|u\.s\.a?\.?)(?![\w])', seg, re.I) or re.search(r'\bUS\b', seg) or \
                re.search(r'(?:,|\s)\s*(%s)\b(?:\s*\d{5}(?:-\d{4})?)?\s*$' % '|'.join(STATES), seg) or US_STATE_NAME.search(low):
            r['country'] = 'US'
        elif US_CITY.search(low) and not city:
            r['country'] = 'US'
    if not r['country'] and US_STATE_NAME.search(low) and not (city and _COUNTRY_RE[city[0]].search(low)):
        r['country'] = 'US'
    if city and (r['country'] in (None, city[0])):
        r['city'] = city[1]
        r['country'] = r['country'] or city[0]
    elif r['country'] and r['country'] != 'US':   # e.g. "Cambridge, United Kingdom": find a city of that country
        for m in _CITY_RE.finditer(low):
            c2 = _CITY.get(m.group(1).lower())
            if c2 and c2[0] == r['country']:
                r['city'] = c2[1]
                break
        if not r['city']:
            for canon, al in C[r['country']][4].items():
                if _alias_re(al).search(low):
                    r['city'] = canon
                    break
    g = _GROUP_RE.search(low)
    if g:
        r['group'] = _group_key(g.group(1))
    elif _EU_WORD.search(seg):
        r['group'] = 'eu'
    elif GLOBAL.search(low) and (r['remote'] or not r['country']):
        r['group'] = 'global'
    return r


def parse(loc):
    """Every place a location string names: 'Bengaluru/Bangalore', 'Remote - EMEA', 'Hybrid, London', 'London, UK',
    'IN-KA-Bengaluru', 'Amsterdam, North Holland, Netherlands', 'Berlin; Munich', 'UK London or Cambridge'."""
    return [dict(p) for p in _parse(loc or '')]


@functools.lru_cache(maxsize=50000)   # a scan sees the same few thousand location strings over and over
def _parse(loc):
    out = []
    for seg in _segments(loc):
        p = parse_one(seg)
        if '/' in seg:   # "Madrid/Barcelona", "Hyderabad/Bangalore": each city counts
            subs = [parse_one(x) for x in seg.split('/') if x.strip()]
            if sum(1 for s in subs if s['country']) >= 2 or (not (p['country'] or p['group']) and any(s['country'] for s in subs)):
                for s in subs:
                    s['remote'] = s['remote'] or p['remote']
                out += subs
                continue
        out.append(p)
    # "UK London or Cambridge": a bare city inherits the country named in the same string
    known = [p['country'] for p in out if p['country']]
    for p in out:
        if not p['country'] and not p['group'] and known:
            hit = next((c for c in known if any(_alias_re(al).search(fold(p['raw']).lower()) for al in C[c][4].values())), None)
            if hit:
                p['country'] = hit
    return tuple(out)


def countries(loc):
    """Country codes a location string names (areas like EMEA not expanded)."""
    return {p['country'] for p in parse(loc) if p['country']}


def describe(loc):
    """Short readable label: 'London, United Kingdom (hybrid)'."""
    bits = []
    for p in parse(loc):
        name = ', '.join(x for x in (p['city'], NAMES.get(p['country'])) if x) or (p['group'] or '').upper()
        if name:
            bits.append(name + (' (remote)' if p['remote'] else ' (hybrid)' if p['hybrid'] else ''))
    return '; '.join(dict.fromkeys(bits))


def country_code(x):
    """'United Kingdom', 'uk', 'GB', 'GBR', 'India' -> code, or None."""
    x = (x or '').strip()
    if not x:
        return None
    up = x.upper()
    if up == 'UK':
        return 'GB'
    if up in C:
        return up
    if up in ISO3:
        return ISO3[up]
    low = fold(x).lower()
    for k, v in C.items():
        if low == v[0].lower() or low in v[1]:
            return k
    return None


def city_of(x):
    """'Bangalore' -> ('IN', 'Bengaluru'); 'Gurgaon' -> ('IN', 'Delhi NCR'); None if unknown."""
    return _CITY.get(fold(x or '').strip().lower())


# ------------------------------------------------------------------ the user's targets

def targets(prof):
    """(countries, cities) the user picked: search.countries / search.cities (names, codes or areas like 'Europe', 'Nordics')."""
    s = prof.get('search') or {}
    cs, cities = set(), set()
    for x in s.get('countries') or []:
        k = country_code(x)
        if k:
            cs.add(k)
        elif (x or '').strip().lower() in GROUPS:
            cs |= GROUPS[x.strip().lower()]
    for x in s.get('cities') or []:
        hit = city_of(x)
        if hit:
            cs.add(hit[0])
            cities.add(hit[1])
        elif x and x.strip():
            cities.add(x.strip())
    return cs, cities


def international(prof):
    """True when the user picked countries in Settings / Welcome (otherwise the original US-first matching runs unchanged)."""
    return bool(targets(prof)[0])


def location_fit(job, prof):
    """For users who picked countries: (keep, why, score change). keep False = outside every country they chose.
    None when the user hasn't picked countries (match.py's original rules apply)."""
    want, cities = targets(prof)
    if not want:
        return None
    loc = job.get('location') or ''
    places = [p for p in parse(loc) if p['country'] or p['group'] or p['remote']]
    if not places:
        return True, '', 0   # no location given: neutral
    ok = []
    for p in places:
        if p['country']:
            if p['country'] in want:
                ok.append(p)
        elif p['group']:
            if p['group'] == 'global' or GROUPS.get(p['group'], set()) & want:
                ok.append(p)
        elif p['remote']:
            ok.append(p)   # "Remote" with no place named
    if not ok:
        named = sorted({NAMES.get(p['country']) or p['group'].upper() for p in places if p['country'] or p['group']})
        return False, 'outside your countries (' + ', '.join(named[:3]) + ')', 0
    if cities:
        hit = [p['city'] for p in ok if p['city'] in cities]
        if hit:
            return True, 'in ' + hit[0], 8
        if all(p['remote'] for p in ok):
            return True, '', 0
        return True, '', -6   # right country, not one of the cities picked: ranked a little lower, never hidden
    return True, '', 0


# ------------------------------------------------------------------ work rights per country
# profile.work_auth = {'GB': 'citizen' | 'authorized' | 'sponsorship', 'EU': ..., 'IN': ...}; 'EU' covers EU/EEA + Switzerland.
STATUS_LABELS = {'citizen': 'Citizen / permanent resident', 'authorized': 'Have a visa or permit to work there',
                 'sponsorship': 'Would need visa sponsorship'}


def status(prof, code):
    """The user's right to work in a country: 'citizen', 'authorized', 'sponsorship', or None if they haven't said."""
    wa = prof.get('work_auth') or {}
    s = wa.get(code)
    if not s and code in EEA:
        s = wa.get('EU')
    if not s and code == 'US':
        if prof.get('needs_sponsorship') is True:
            return 'sponsorship'
        if prof.get('work_authorized_us') is True and prof.get('needs_sponsorship') is False:
            return 'authorized'
    return s if s in STATUS_LABELS else None


def has_rights(prof, code):
    s = status(prof, code)
    return None if s is None else s in ('citizen', 'authorized')


_PLACE = (r"(?:the\s+)?(?:uk|u\.k\.|united kingdom|great britain|britain|eu|e\.u\.|eea|european union|europe|schengen|"
          + '|'.join(re.escape(v[0].lower()) for k, v in C.items() if k != 'US') + r"|"
          + '|'.join(re.escape(c) for c in ('deutschland', 'nederland', 'holland', 'schweiz', 'suisse')) + r"|country of employment|"
          r"(?:the\s+)?country (?:where|in which) (?:the role|you|this role)[\w ]{0,20})")
RIGHT_TO_WORK = re.compile(
    r"(?:must|should|need to|needs to|will need to|required to|have to)\s+(?:already\s+)?(?:have|hold|possess|be able to demonstrate|"
    r"provide proof of)\s+(?:the\s+|a\s+|full\s+|valid\s+|existing\s+|unrestricted\s+|permanent\s+)*(?:legal\s+)?"
    r"(?:right to work|work(?:ing)? (?:permit|authori[sz]ation|rights?)|residence permit)\s+(?:in|for|within)\s+(" + _PLACE + r")|"
    r"(?:right to work|work permit|work authori[sz]ation)\s+(?:in|for|within)\s+(" + _PLACE + r")\s+(?:is\s+)?(?:required|essential|mandatory|needed|a must)|"
    r"(?:eligible|authori[sz]ed|permitted|entitled|able)\s+to\s+work\s+(?:in|within)\s+(" + _PLACE + r")\s+(?:without|with no)\s+(?:the need for\s+)?(?:visa\s+)?sponsorship|"
    r"\b(eu|eea|uk|british|indian|swiss)\s+(?:citizens?|nationals?|passport holders?)\s+only|"
    r"(?:only|exclusively)\s+(?:open|available)\s+to\s+(eu|eea|uk|indian)\s+(?:citizens?|nationals?|residents?)", re.I)
NO_SPONSOR = re.compile(
    r"(?:do not|don't|does not|cannot|can't|can not|unable to|will not|won't|not able to|are not able to|is not able to|are unable to)\s+"
    r"(?:currently\s+)?(?:offer|provide|support|sponsor|consider)[\w\s,/-]{0,40}?(?:visa|sponsorship|work permits?|relocation and visa)|"
    r"\bno\s+(?:visa\s+)?sponsorship\b|sponsorship\s+(?:is\s+)?not\s+(?:available|offered|provided|possible)|"
    r"(?:without|not)\s+(?:requiring|require|needing|the need for)\s+(?:visa\s+)?sponsorship|visa sponsorship (?:is )?not available", re.I)
_PLACE_CODE = {'uk': 'GB', 'u.k.': 'GB', 'united kingdom': 'GB', 'great britain': 'GB', 'britain': 'GB', 'british': 'GB', 'eu': 'EU',
               'e.u.': 'EU', 'eea': 'EU', 'european union': 'EU', 'europe': 'EU', 'schengen': 'EU', 'indian': 'IN', 'swiss': 'CH',
               'deutschland': 'DE', 'nederland': 'NL', 'holland': 'NL', 'schweiz': 'CH', 'suisse': 'CH'}


def _where(word, job_cs):
    w = re.sub(r'^the\s+', '', (word or '').strip().lower())
    if not w or w.startswith('country'):
        return sorted(job_cs)
    k = _PLACE_CODE.get(w) or country_code(w)
    return [k] if k else sorted(job_cs)


def abroad(job):
    """True when every place the posting names is outside the US (and it names at least one)."""
    cs = countries(job.get('location') or '')
    return bool(cs) and 'US' not in cs


def work_rights(job, prof):
    """(abroad, reason). For a posting outside the US, reason is a ready-to-log Skipped reason when it needs local work
    rights the user said they don't have ('sponsorship'); '' otherwise. Unknown status never skips (the agent applies)."""
    cs = countries(job.get('location') or '')
    if not cs or 'US' in cs:
        return False, ''
    text = f"{job.get('title', '')}\n{job.get('description') or ''}"
    need = []
    m = RIGHT_TO_WORK.search(text)
    if m:
        need = _where(next((g for g in m.groups() if g), ''), cs)
    elif NO_SPONSOR.search(text):
        need = sorted(cs)
    for code in need:
        if code == 'EU':
            hit = [c for c in cs if c in EEA] or ['DE']
            s = [status(prof, c) for c in hit]
            if s and all(x == 'sponsorship' for x in s):
                return True, 'Needs the right to work in the EU/EEA, and you said you would need sponsorship there'
            continue
        if status(prof, code) == 'sponsorship' and (len(need) == 1 or all(status(prof, c) == 'sponsorship' for c in need)):
            return True, f'Needs the right to work in {short(code)} (no visa sponsorship), and you said you would need sponsorship there'
    return True, ''


def rights_note(job, prof):
    """A softer note when the posting needs local work rights and the user hasn't said whether they have them."""
    cs = countries(job.get('location') or '')
    if not cs or 'US' in cs:
        return ''
    text = f"{job.get('title', '')}\n{job.get('description') or ''}"
    m = RIGHT_TO_WORK.search(text)
    need = _where(next((g for g in m.groups() if g), ''), cs) if m else (sorted(cs) if NO_SPONSOR.search(text) else [])
    unknown = [c for c in need if (status(prof, c) if c != 'EU' else status(prof, 'DE')) is None]
    if unknown:
        return f'needs the right to work in {short(unknown[0])} (add your status in Settings)'
    return ''


def short(code):
    return {'GB': 'the UK', 'US': 'the US', 'EU': 'the EU/EEA', 'NL': 'the Netherlands', 'AE': 'the UAE'}.get(code, NAMES.get(code, code))


# ------------------------------------------------------------------ program names by country
PROGRAMS = [   # key, label, title pattern; the first three are internship-like, the rest early-career full-time
    ('placement', 'Placement year', re.compile(r'\b(placement year|industrial placement|year in industry|sandwich (?:year|placement|student)|'
                                              r'(?:12|13|6|9)[- ]month placement|work placement|placement student|'
                                              r'(?<!campus )(?<!pre-)(?<!pre )placement(?! (?:officer|manager|coordinator|specialist|consultant|'
                                              r'advisor|lead|drive|cell)))\b', re.I)),
    ('working_student', 'Working student (Werkstudent)', re.compile(r'\b(werkstudent(?:in)?|werkstudierende[rn]?|working student|'
                                                                    r'studentische (?:hilfskraft|aushilfe)|student assistant|student worker|'
                                                                    r'student job|part[- ]time student)\b', re.I)),
    ('internship', 'Internship', re.compile(r"\b(intern|interns|internship|praktikum|praktikant(?:in)?|pflichtpraktikum|stagiaire|stagiair|"
                                           r"tirocinio|tirocinante|pr[aá]cticas|becario|sta[zż](?:ysta)?|praktik|harjoittelija|"
                                           r"sde[- ]?intern|summer (?:analyst|associate))\b|^stage\s*[-–:|(]|\bstage (?:de|d'|en|ingenieur|"
                                           r"ingénieur|developpeur|développeur|data|business|marketing|finance)\b|\b(?:4|5|6) mois\b", re.I)),
    ('graduate_scheme', 'Graduate scheme', re.compile(r'\b(graduate (?:scheme|programme|program|trainee|analyst|engineer|developer|'
                                                     r'software engineer|consultant|associate)|grad scheme|trainee programme|management trainee|'
                                                     r'absolvent(?:enprogramm)?|berufseinstieg|direkteinstieg|young professional|'
                                                     r'graduate engineer trainee)\b', re.I)),
    ('campus', 'Campus / off-campus hiring', re.compile(r'\b(campus (?:hire|hiring|recruitment|drive|placement)|off[- ]campus|on[- ]campus|'
                                                       r'freshers?|university hire|sde[- ]?(?:1|i)\b(?! ?intern)|new grad)\b', re.I)),
]
INTERN_LIKE = ('placement', 'working_student', 'internship')
PPO = re.compile(r'\b(ppo|pre[- ]placement offer)\b', re.I)


def program(title):
    """Which kind of program a title names ('placement', 'working_student', 'internship', 'graduate_scheme', 'campus'), or ''.
    Checked in that order: an "SDE Intern - Campus Hiring" is an internship, a "Placement Year Intern" a placement."""
    title = title or ''
    for key, _label, rx in PROGRAMS:
        if rx.search(title):
            return key
    if re.search(r'\bGET\b', title):   # Graduate Engineer Trainee (India), uppercase only
        return 'graduate_scheme'
    return ''


def intern_like(title):
    return program(title) in INTERN_LIKE


def grad_program(title):
    return program(title) in ('graduate_scheme', 'campus')


def program_label(key):
    return next((l for k, l, _ in PROGRAMS if k == key), '')


def program_gate(job, prof):
    """(reject_reason, note). reject when the user picked program types and this one isn't among them; note names the
    local program ('placement year', 'Werkstudent', 'PPO') for the why line."""
    title = job.get('title') or ''
    key = program(title)
    picked = [p for p in ((prof.get('search') or {}).get('programs') or []) if p]
    note = program_label(key).lower() if key in ('placement', 'working_student', 'graduate_scheme') else ''
    if key == 'campus' and re.search(r'campus|fresher', title, re.I):
        note = 'campus hiring'
    if PPO.search(f"{title} {(job.get('description') or '')[:3000]}"):
        note = (note + ', ' if note else '') + 'PPO possible'
    if picked and key and key not in picked and not (key == 'internship' and 'internship' in picked):
        return f'{program_label(key).lower()} (not one of the program types you picked)', note
    return '', note


# ------------------------------------------------------------------ application questions asked outside the US

def _yn(b):
    return '' if b is None else ('Yes' if b else 'No')


def _rights_answer(prof, code):
    s = status(prof, code) if code != 'EU' else ((prof.get('work_auth') or {}).get('EU') or None)
    return '' if s is None else ('No' if s == 'sponsorship' else 'Yes')


def _sponsor_answer(prof, code):
    s = status(prof, code) if code != 'EU' else ((prof.get('work_auth') or {}).get('EU') or None)
    return '' if s is None else ('Yes' if s == 'sponsorship' else 'No')


def _citizen_answer(p, code):
    """From the nationality the user typed ('India', 'India, United Kingdom'); blank when they haven't said."""
    nat = [country_code(x) for x in re.split(r'[,;/&]| and ', p.get('nationality') or '') if x.strip()]
    if not nat or None in nat:
        return ''
    return 'Yes' if (code in nat or (code == 'EU' and set(nat) & EEA)) else 'No'


def answer_rows(p):
    """Extra answer-bank rows (same shape as answers.default_bank). Right to work / sponsorship per country the user
    targets or has a status for (plus the UK, EU and India, the common ones), and the questions European and Indian forms
    ask. Blank = not in the profile yet: the agent asks the user."""
    want, _ = targets(p)
    codes = ['GB', 'EU', 'IN'] + sorted((set(want) | set((p.get('work_auth') or {}))) - {'GB', 'EU', 'IN', 'US'})
    rows = []
    for code in codes:
        name = 'the EU/EEA' if code == 'EU' else short(code)
        rows.append((f'work_auth_{code}', f'Do you have the right to work in {name}?', None, _rights_answer(p, code)))
        rows.append((f'sponsor_{code}', f'Will you need visa sponsorship to work in {name}?', None, _sponsor_answer(p, code)))
        rows.append((f'citizen_{code}', f'Are you a citizen of {name}?', None, _citizen_answer(p, code)))
    cit = (p.get('citizenship') or '').lower()
    nat = p.get('nationality') or ('United States' if re.match(r'\s*u\.?s\.? citizen', cit) else '')
    cgpa = p.get('cgpa') or (p.get('gpa') if str(p.get('gpa_scale') or '') == '10' else '')
    rows += [
        ('nationality', 'What is your nationality?', r'nationalit|country of citizenship|citizen of which|which countr(?:y|ies).{0,20}citizen', nat),
        ('notice_period', 'What is your notice period?', r'notice period|how soon can you join|joining (?:time|period)|days to join|'
                                                          r'earliest (?:date of )?joining', p.get('notice_period', '')),
        ('current_ctc', 'What is your current CTC?', r'current (?:ctc|cost to company|annual (?:ctc|package|salary)|package|compensation|'
                                                      r'salary|stipend)|\bcctc\b|present (?:ctc|salary)', p.get('current_ctc', '')),
        ('expected_ctc', 'What is your expected CTC?', r'expected (?:ctc|cost to company|package)|\bectc\b', p.get('expected_ctc', '')),
        ('expected_salary_local', 'Expected salary (local currency)', r'(?:expected|desired) (?:annual |gross |monthly )?(?:salary|stipend|pay)'
                                                                     r'[^?]{0,30}(?:gbp|eur|chf|sek|nok|dkk|pln|inr|sgd|aed|aud|cad|£|€|₹|lpa)|'
                                                                     r'salary expectations? (?:in|\()\s*(?:gbp|eur|chf|sek|nok|dkk|pln|inr|£|€|₹)|'
                                                                     r'\bstipend expect|gehaltsvorstellung', p.get('expected_salary_local', '')),
        ('gdpr', 'Do you consent to the processing of your personal data (GDPR)?',
         r'\bgdpr\b|data protection|process(?:ing)? (?:of )?(?:my|your) (?:personal )?(?:data|information)|(?:retain|keep|store) (?:my|your) '
         r'(?:data|details|application|cv)|talent (?:pool|community)|privacy consent|datenschutz', 'No' if p.get('gdpr_ok') is False else 'Yes'),
        ('marks_10th', '10th (Class X / SSC) marks', r'\b(?:10th|tenth|ssc|class x|matriculation|secondary school certificate)\b', p.get('marks_10th', '')),
        ('marks_12th', '12th (Class XII / HSC) marks', r'\b(?:12th|twelfth|hsc|class xii|higher secondary)\b|\b(?:intermediate|puc)\b[^?]{0,20}'
                                                        r'(?:marks|percentage|score|cgpa)', p.get('marks_12th', '')),
        ('cgpa', 'CGPA (out of 10)', r'\bcgpa\b|gpa (?:out of|on a scale of) 10|percentage in (?:graduation|degree|b\.?tech|b\.?e)', cgpa),
        ('gpa_scale', 'GPA scale', r'gpa scale|scale (?:of|for) (?:your )?gpa|out of (?:what|how many)', p.get('gpa_scale', '')),
        ('languages', 'Which languages do you speak, and how well?',
         r'(?:german|french|dutch|spanish|polish|swedish|danish|norwegian|finnish|italian|portuguese|hindi)[^?]{0,30}'
         r'(?:proficien|level|fluen|skills?)|(?<!programming )(?<!coding )language (?:proficiency|level)|(?:speak|fluent in|proficiency in|knowledge of) (?:german|french|dutch|spanish|polish|swedish|'
         r'danish|norwegian|finnish|italian|portuguese)|languages? (?:do you speak|spoken|skills)|deutschkenntnisse', p.get('languages', '')),
        ('visa_type', 'What visa or permit do you hold?', r'(?:type of|which|what) (?:visa|work permit|residence permit)(?! sponsor)|visa type',
         p.get('visa_type', '')),
        ('relocate_abroad', 'Are you willing to relocate to another country for this role?', None, _yn(p.get('willing_to_relocate'))),
        ('phone_country_code', 'Phone country code', r'country (?:dial(?:l)?ing |calling |phone )?code|dial(?:l)?ing code|phone (?:country )?code|'
                                                      r'country prefix', phone_code(p)),
    ]
    return [{"key": k, "question": q, "pattern": pat, "answer": a, "source": "profile"} for k, q, pat, a in rows]


def phone_code(p):
    ph = (p.get('phone') or '').strip()
    m = re.match(r'\+(\d{1,3})', ph)
    if m:
        code = '+' + m.group(1)
        hit = next((k for k, d in DIAL.items() if d == code and k != 'CA'), None)
        return f'{code} ({NAMES[hit]})' if hit else code
    k = country_code(p.get('country') or '')
    return f'{DIAL[k]} ({NAMES[k]})' if k else ''


DEMONYM = {'british': 'GB', 'irish': 'IE', 'german': 'DE', 'dutch': 'NL', 'french': 'FR', 'swiss': 'CH', 'swedish': 'SE', 'norwegian': 'NO',
           'danish': 'DK', 'finnish': 'FI', 'spanish': 'ES', 'portuguese': 'PT', 'italian': 'IT', 'belgian': 'BE', 'austrian': 'AT',
           'polish': 'PL', 'indian': 'IN', 'singaporean': 'SG', 'emirati': 'AE', 'australian': 'AU', 'canadian': 'CA'}


def named_country(q):
    """The country (or 'EU') a question names, or None. 'right to work in the UK' -> 'GB'."""
    low = fold(q or '').lower()
    for w, k in (('european union', 'EU'), ('eu/eea', 'EU'), ('eea', 'EU'), ('schengen', 'EU')):
        if w in low:
            return k
    if re.search(r'(?<![\w-])eu(?![\w-])', low):
        return 'EU'
    m = re.search(r'\b(%s)\b' % '|'.join(DEMONYM), low)
    if m:
        return DEMONYM[m.group(1)]
    for k, rx in _COUNTRY_RE.items():
        if k != 'US' and rx.search(low):
            return k
    return None


def match(q, bank, options=None):
    """Answers the international questions before the general matcher runs; None for anything else. Right to work and
    sponsorship for a named country (never the US answer for a UK question), notice period, CTC, salary in local currency,
    GDPR consent, nationality, 10th/12th marks, CGPA, languages."""
    from . import answers as ans
    q = (q or '').strip()
    if not q:
        return None
    rows = {r.get('key'): r for r in bank}
    low = q.lower()
    code = named_country(q)

    def out(key, answer, label):
        if answer in (None, ''):
            return {"question": q, "answer": None, "confidence": 0.9, "key": key,
                    "action": f"ask the user ({label}), then applytwin_save_answer"}
        return {"question": q, "answer": ans.pick_option(answer, options) if options else answer, "confidence": 0.92, "key": key}

    if code:
        k = code if code == 'EU' or f'work_auth_{code}' in rows else ('EU' if code in EEA else code)
        rights = (rows.get(f'work_auth_{k}') or {}).get('answer', '')
        spons = (rows.get(f'sponsor_{k}') or {}).get('answer', '')
        place = short(k)
        works = re.search(r'right to work|(?:authori[sz]ed|eligible|permitted|entitled|allowed|legally able) to work|work (?:permit|authori[sz]ation)|'
                          r'work rights|legally work', low)
        if works and re.search(r'sponsor', low):   # "authorized to work in the UK without sponsorship?"
            if rights and spons:
                return out(f'work_auth_{k}', 'Yes' if rights == 'Yes' and spons == 'No' else 'No', f'right to work in {place}')
            return out(f'work_auth_{k}', '', f'right to work in {place} without sponsorship')
        if works:
            return out(f'work_auth_{k}', rights, f'right to work in {place}')
        if re.search(r'sponsor|visa', low) and not re.search(r'type of|which visa|what visa', low):
            return out(f'sponsor_{k}', spons, f'visa sponsorship for {place}')
        if re.search(r'relocat', low):
            return out('relocate_abroad', (rows.get('relocate_abroad') or {}).get('answer', ''), f'relocating to {place}')
        if re.match(r'\s*(are|do|is|have)\b', low) and re.search(r'citizen|nationalit|passport', low):   # "Are you an EU citizen?"
            return out(f'citizen_{k}', (rows.get(f'citizen_{k}') or {}).get('answer', ''), f'citizenship of {place}')
    if re.search(r'\bshare code\b|right to work (?:share )?code|brp number|biometric residence|aadhaar|\bpan (?:card|number)\b|passport number|'
                 r'national insurance number|\bni number\b|\buan\b', low):
        return {"question": q, "answer": None, "confidence": 0, "key": None, "action": "ask the user, then applytwin_save_answer",
                "how": ans.ASK_HOW}
    for key in ('notice_period', 'current_ctc', 'expected_ctc', 'expected_salary_local', 'gdpr', 'marks_10th', 'marks_12th', 'cgpa',
                'gpa_scale', 'languages', 'visa_type', 'nationality', 'phone_country_code'):
        r = rows.get(key)
        if not r:
            continue
        pat = _PATTERNS.get(key) or r.get('pattern')
        try:
            if pat and re.search(pat, q, re.I):
                label = r.get('question') or key
                return out(key, r.get('answer'), label)
        except re.error:
            continue
    return None


_PATTERNS = {r['key']: r['pattern'] for r in answer_rows({})}


# ------------------------------------------------------------------ resume / CV conventions

def conventions(country=None, prof=None):
    """How a resume is usually presented where the job is. tailor.py / render.py read this; nothing here changes content.
      doc       'CV' (UK, Europe, India, most of the world) or 'Resume' (US, Canada)
      paper     'A4' everywhere except the US and Canada ('Letter')
      photo     False: ApplyTwin never adds a photo (optional in parts of Europe; never needed to apply)
      gpa_label 'CGPA' in India (scale out of 10 shown as written), else 'GPA'
      date_fmt  how dates are written on forms ('DD/MM/YYYY' in the UK, Europe and India)
      extras    fields forms there sometimes ask for"""
    k = country_code(country) or country or 'US'
    us = k in ('US', 'CA')
    india = k == 'IN'
    return {
        'country': k, 'doc': 'Resume' if us else 'CV', 'paper': 'Letter' if us else 'A4', 'photo': False,
        'gpa_label': 'CGPA' if india else 'GPA', 'gpa_scale': '10' if india else ('4.0' if us else ''),
        'date_fmt': 'MM/DD/YYYY' if k == 'US' else ('YYYY-MM-DD' if k in ('SE', 'CA') else 'DD/MM/YYYY'),
        'phone': DIAL.get(k, ''), 'currency': CURRENCY.get(k, ''),
        'extras': (['10th and 12th marks', 'CGPA out of 10', 'notice period', 'current and expected CTC (LPA)'] if india else
                   ['right to work', 'notice period', 'expected salary in local currency', 'GDPR consent'] if k in EUROPE else []),
    }


def job_country(job):
    """The one country a posting is in, or None when it names none or several."""
    cs = countries((job or {}).get('location') or '')
    return next(iter(cs)) if len(cs) == 1 else None


def apply_conventions(res, job, prof=None):
    """Set the page size and labels a tailored resume should use for this job's country, in place: res['paper'] ('A4' or
    'Letter') and, for India, education 'gpa_label' = 'CGPA' when the GPA is written out of 10. Returns the conventions.
    Content is never changed."""
    conv = conventions(job_country(job))
    res['paper'] = conv['paper']
    if conv['gpa_label'] == 'CGPA':
        for e in res.get('education') or []:
            g = str(e.get('gpa') or '')
            m = re.match(r'\s*(\d+(?:\.\d+)?)', g)
            if m and (4.3 < float(m.group(1)) <= 10 or re.search(r'/\s*10\b', g)):
                e['gpa_label'] = 'CGPA'
                if '/' not in g:
                    e['gpa'] = g.strip() + '/10'
    return conv


def file_label(job):
    """'CV' or 'Resume', for the PDF's file name (Jane_Doe_CV.pdf for a London job)."""
    return conventions(job_country(job))['doc']


def paper_css(paper):
    """Extra CSS for an A4 page (the base stylesheet is US Letter)."""
    if str(paper or '').upper() != 'A4':
        return ''
    return '@page { size: A4; margin: 0; } .page { width: 210mm; min-height: 297mm; }'


def format_date(value, country=None):
    """'2027-05-15' / '05/15/2027' (US order) -> the local order ('15/05/2027'); text without a full date comes back unchanged."""
    v = (value or '').strip()
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', v) or None
    if m:
        y, mo, d = m.groups()
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', v)
        if not m:
            return v
        mo, d, y = m.groups()
    fmt = conventions(country)['date_fmt']
    d, mo = d.zfill(2), mo.zfill(2)
    return {'MM/DD/YYYY': f'{mo}/{d}/{y}', 'YYYY-MM-DD': f'{y}-{mo}-{d}'}.get(fmt, f'{d}/{mo}/{y}')


# ------------------------------------------------------------------ choices for the Welcome / Settings screens

def choices():
    """Countries, areas, cities and program types for the UI pickers."""
    feat = ['GB', 'IE', 'DE', 'NL', 'FR', 'CH', 'SE', 'NO', 'DK', 'FI', 'ES', 'PL', 'IN', 'CA', 'SG', 'AE', 'AU', 'US']
    return {
        'countries': [{'code': k, 'name': NAMES[k], 'region': C[k][3]} for k in feat] +
                     [{'code': k, 'name': NAMES[k], 'region': C[k][3]} for k in sorted(C, key=lambda c: NAMES[c]) if k not in feat],
        'areas': [{'key': 'europe', 'name': 'All of Europe'}, {'key': 'eu', 'name': 'EU / EEA'}, {'key': 'nordics', 'name': 'Nordics'},
                  {'key': 'dach', 'name': 'Germany, Austria, Switzerland'}],
        'cities': {k: list(C[k][4]) for k in C if C[k][4]},
        'programs': [{'key': k, 'label': l} for k, l, _ in PROGRAMS],
        'statuses': [{'key': k, 'label': v} for k, v in STATUS_LABELS.items()],
        'eea': sorted(EEA),
        'groups': {k: sorted(v) for k, v in GROUPS.items() if k in ('europe', 'eu', 'nordics', 'dach')},
    }
