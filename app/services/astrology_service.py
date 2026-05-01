import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, Any, List, TypedDict
from app.types.astrology import *


"""
Service principal de calcul astrologique basé sur Swiss Ephemeris.

Responsabilités :
- Calcul du thème natal
- Calcul des aspects
- Génération des transits futurs

"""
class AstrologyService:
    
    # ======================================================== #
    """ Initialise le moteur astrologique et les constantes. """
    def __init__(self):
        swe.set_ephe_path('/usr/share/ephe') 
        
        self.planets = {
            "Soleil": swe.SUN,
            "Lune": swe.MOON,
            "Mercure": swe.MERCURY,
            "Vénus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturne": swe.SATURN,
            "Uranus": swe.URANUS,
            "Neptune": swe.NEPTUNE,
            "Pluton": swe.PLUTO
        }

        self.signs = [
            "Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge",
            "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons"
        ]


    # ==================================================================== #
    """ Convertit une datetime en Julian Day. Returns: float: Julian Day """
    def _get_date_to_jd(self, dt: datetime) -> float:
        return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
    
    
    # ============================================================ #
    """ Retourne le signe astrologique à partir d'une longitude. """
    def _get_sign(self, lon: float) -> str:
        return self.signs[int(lon / 30)]
    
    
    # ==================================== #
    """ Formate une position planétaire. """
    def _format_position(self, lon: float) -> PlanetPosition:
        return {
            "lon": lon,
            "sign": self._get_sign(lon),
            "deg": round(lon % 30, 2)
        }


    # =============================================== #
    """ Calcule les aspects majeurs entre planètes. """
    def _calculate_aspects(self, planets: Dict[str, PlanetPosition]) -> List[Aspect]:
        major_aspects = {
            0: "Conjonction",
            60: "Sextile",
            90: "Carré",
            120: "Trigone",
            180: "Opposition"
        }

        results: List[Aspect] = []
        names = list(planets.keys())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                p1, p2 = names[i], names[j]

                diff = abs(planets[p1]["lon"] - planets[p2]["lon"])
                if diff > 180:
                    diff = 360 - diff

                for angle, aspect_name in major_aspects.items():
                    orb = abs(diff - angle)
                    if orb <= 5:
                        results.append({
                            "p1": p1,
                            "p2": p2,
                            "type": aspect_name,
                            "orb": round(orb, 2)
                        })

        return results


    # ================================================================ #
    """ Génère les transits des 12 prochains mois (planètes lentes). """
    def _calculate_future_transits(self) -> List[Transit]:
        slow_planets = {
            "Jupiter": swe.JUPITER,
            "Saturne": swe.SATURN,
            "Pluton": swe.PLUTO
        }

        forecast: List[Transit] = []
        now = datetime.utcnow()

        for i in range(1, 13):
            future_date = now + timedelta(days=i * 30)
            jd = self._get_date_to_jd(future_date)

            positions = {}
            for name, p_id in slow_planets.items():
                lon = swe.calc_ut(jd, p_id)[0]
                positions[name] = self._get_sign(lon)

            forecast.append({
                "month": future_date.strftime("%B %Y"),
                "positions": positions
            })

        return forecast


    # =============================================== #
    """ Génère le thème natal complet + prévisions. """
    def get_full_chart(self, birth_date: datetime, lat: float, lon: float) -> FullChart:
        jd = self._get_date_to_jd(birth_date)

        # ================= PLANÈTES ================= #
        planet_data: Dict[str, PlanetPosition] = {}

        for name, p_id in self.planets.items():
            res = swe.calc_ut(jd, p_id)[0]
            planet_data[name] = self._format_position(res)

        # ================= NOEUDS ================= #
        nodes = swe.calc_ut(jd, swe.TRUE_NODE)[0]

        planet_data["Noeud Nord"] = self._format_position(nodes)

        south_node = (nodes + 180) % 360
        planet_data["Noeud Sud"] = self._format_position(south_node)

        # ================= MAISONS ================= #
        houses, ascmc = swe.houses(jd, lat, lon, b'P')

        houses_data: Dict[int, House] = {
            i + 1: {
                "lon": h,
                "sign": self._get_sign(h)
            }
            for i, h in enumerate(houses)
        }

        ascendant = self._format_position(ascmc[0])

        # ================= ASPECTS ================= #
        aspects = self._calculate_aspects(planet_data)

        # ================= TRANSITS ================= #
        transits = self._calculate_future_transits()

        return {
            "birth_chart": {
                "planets": planet_data,
                "ascendant": ascendant,
                "houses": houses_data,
                "aspects": aspects
            },
            "forecast": transits
        }
