"""Tunable settings. Change these, not the logic."""

SCRAPER_VERSION = "0.1.0"

# Budget, INCLUDING VAT (a private buyer pays the VAT on "+VAT" listings).
PRICE_PREFERRED_INC_VAT = 25_000
PRICE_CEILING_INC_VAT = 32_000

# Battery thresholds (kWh). Below ~80kWh a large van gets roughly 100 real
# miles (less in winter) -- needs a charging stop on a ~130-mile trip.
# Early e-Boxers shipped with 37 or 75kWh packs;
# current large vans are ~68-110kWh.
SMALL_BATTERY_KWH = 80
BIG_BATTERY_KWH = 90

# Below this many miles/year on a 2+ year old van, suggest an MOT-history check.
LOW_MILES_PER_YEAR = 2_000

# Politeness. We identify ourselves honestly, respect robots.txt, and pause
# between requests to the same host.
USER_AGENT = ("van-scraper/0.1 (personal weekly used-van search; "
              "+https://github.com/james-westwood)")
REQUEST_DELAY_S = 2.0
TIMEOUT_S = 30.0

# Discovery pages on the AA that robots.txt allows. Each shows only a sample
# (~6-15 vans); the full search (/used-cars/displaycars) is DISALLOWED by
# robots.txt and must not be used. Coverage is therefore partial.
AA_BROWSE_PAGES = [
    "https://www.theaa.com/used-vans/electric",
    "https://www.theaa.com/used-vans/bodystyle/high-roof-vans",
    "https://www.theaa.com/used-vans/large-vans",
    "https://www.theaa.com/used-vans/peugeot/boxer",
    "https://www.theaa.com/used-vans/citroen/relay",
    "https://www.theaa.com/used-vans/vauxhall/movano",
    "https://www.theaa.com/used-vans/fiat/ducato",
    "https://www.theaa.com/used-vans/ford/transit",
    "https://www.theaa.com/used-vans/mercedes/sprinter",
]
