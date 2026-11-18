"""Solar position from date, time and location (our own implementation of the NOAA formulas).

No 3ds Max calls here, so it runs and tests outside Max.
Accuracy: about 0.1 degree between 1950 and 2050, which is plenty for archviz.
"""
import datetime
import math

# A few presets so users and Claude can type a city instead of coordinates.
CITIES = {
    "amsterdam": (52.37, 4.90, 1), "berlin": (52.52, 13.40, 1), "cairo": (30.04, 31.24, 2),
    "dubai": (25.20, 55.27, 4), "istanbul": (41.01, 28.98, 3), "london": (51.51, -0.13, 0),
    "los angeles": (34.05, -118.24, -8), "madrid": (40.42, -3.70, 1), "new york": (40.71, -74.01, -5),
    "paris": (48.86, 2.35, 1), "riyadh": (24.71, 46.68, 3), "rome": (41.90, 12.50, 1),
    "singapore": (1.35, 103.82, 8), "sydney": (-33.87, 151.21, 10), "tokyo": (35.68, 139.69, 9),
    "toronto": (43.65, -79.38, -5), "amman": (31.95, 35.93, 3), "beirut": (33.89, 35.50, 2),
}


def parse_date(text):
    return datetime.datetime.strptime(str(text).strip(), "%Y-%m-%d").date()


def parse_time(text):
    t = str(text).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%H"):
        try:
            return datetime.datetime.strptime(t, fmt).time()
        except ValueError:
            pass
    raise ValueError("time must be HH:MM, got %r" % text)


def sun_position(date, time, latitude, longitude, utc_offset=0.0, refraction=True):
    """Return (azimuth, elevation) in degrees.

    date: datetime.date or 'YYYY-MM-DD'; time: datetime.time or 'HH:MM' (local clock time);
    latitude north positive, longitude east positive; utc_offset in hours (include daylight saving).
    Azimuth: 0 = north, 90 = east (clockwise seen from above). Elevation: 0 = horizon.
    """
    if not isinstance(date, datetime.date):
        date = parse_date(date)
    if not isinstance(time, datetime.time):
        time = parse_time(time)
    local = datetime.datetime.combine(date, time)
    utc = local - datetime.timedelta(hours=float(utc_offset))
    # Julian day
    y, m = utc.year, utc.month
    d = utc.day + (utc.hour + utc.minute / 60.0 + utc.second / 3600.0) / 24.0
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    t = (jd - 2451545.0) / 36525.0  # Julian centuries since J2000

    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0         # mean longitude
    m_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)                # mean anomaly
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)                # orbit eccentricity
    mr = math.radians(m_anom)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long)))

    yv = math.tan(math.radians(eps / 2.0)) ** 2
    l0r = math.radians(l0)
    eq_time = 4.0 * math.degrees(yv * math.sin(2 * l0r) - 2 * e * math.sin(mr)
                                 + 4 * e * yv * math.sin(mr) * math.cos(2 * l0r)
                                 - 0.5 * yv * yv * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    minutes_utc = utc.hour * 60.0 + utc.minute + utc.second / 60.0
    true_solar = (minutes_utc + eq_time + 4.0 * float(longitude)) % 1440.0
    hour_angle = true_solar / 4.0 - 180.0
    if hour_angle < -180.0:
        hour_angle += 360.0

    lat = math.radians(float(latitude))
    ha = math.radians(hour_angle)
    cos_zen = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    cos_zen = max(-1.0, min(1.0, cos_zen))
    zen = math.acos(cos_zen)
    elevation = 90.0 - math.degrees(zen)

    az_den = math.cos(lat) * math.sin(zen)
    if abs(az_den) > 1e-9:
        cos_az = ((math.sin(lat) * math.cos(zen)) - math.sin(decl)) / az_den
        cos_az = max(-1.0, min(1.0, cos_az))
        az = 180.0 - math.degrees(math.acos(cos_az))
        if hour_angle > 0:
            az = -az
        azimuth = az % 360.0
    else:
        azimuth = 180.0 if latitude > 0 else 0.0

    if refraction and elevation > -0.575:
        te = math.tan(math.radians(elevation))
        if elevation > 85.0:
            corr = 0.0
        elif elevation > 5.0:
            corr = 58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5
        else:
            corr = 1735.0 + elevation * (-518.2 + elevation * (103.4 + elevation * (-12.79 + elevation * 0.711)))
        elevation += corr / 3600.0
    return round(azimuth, 3), round(elevation, 3)


def scene_azimuth(solar_azimuth, north=0.0):
    """Turn a compass azimuth into the scene azimuth used by the Sun module.

    north: where true north points in the scene, degrees clockwise from +Y (0 = +Y is north).
    """
    return (float(solar_azimuth) + float(north)) % 360.0


def find_city(name):
    return CITIES.get(str(name).strip().lower())
