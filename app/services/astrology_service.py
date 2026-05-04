import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, Any, List, TypedDict
from app.types.astrology import *


class AstrologyService:
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


    def _get_date_to_jd(self, dt: datetime) -> float:
        return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)
    
    
    def _extract_lon(self, result):
        if isinstance(result, tuple):
            result = result[0]

        if isinstance(result, (list, tuple)):
            return float(result[0])

        return float(result)
    
    
    def _get_sign(self, lon: float) -> str:
        lon = float(lon)
        return self.signs[int(lon // 30)]
    
    
    def _format_position(self, lon: float):
        lon = float(lon)
        return {
            "lon": lon,
            "sign": self._get_sign(lon),
            "deg": round(lon % 30, 2)
        }


    def _calculate_aspects(self, planets: Dict[str, Any]):
        major_aspects = {
            0: "Conjonction",
            60: "Sextile",
            90: "Carré",
            120: "Trigone",
            180: "Opposition"
        }

        results = []
        names = list(planets.keys())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                p1, p2 = names[i], names[j]

                diff = abs(planets[p1]["lon"] - planets[p2]["lon"])
                diff = diff if diff <= 180 else 360 - diff

                for angle, name in major_aspects.items():
                    orb = abs(diff - angle)

                    if orb <= 5:
                        results.append({
                            "p1": p1,
                            "p2": p2,
                            "type": name,
                            "orb": round(orb, 2)
                        })

        return results


    def _calculate_future_transits(self):
        slow_planets = {
            "Jupiter": swe.JUPITER,
            "Saturne": swe.SATURN,
            "Pluton": swe.PLUTO
        }

        forecast = []
        now = datetime.utcnow()

        for i in range(1, 13):
            future = now + timedelta(days=i * 30)
            jd = self._get_date_to_jd(future)

            positions = {}

            for name, pid in slow_planets.items():
                result = swe.calc_ut(jd, pid)
                lon = self._extract_lon(result)

                positions[name] = {
                    "lon": lon,
                    "sign": self._get_sign(lon)
                }

            forecast.append({
                "month": future.strftime("%B %Y"),
                "positions": positions
            })

        return forecast


    def get_full_chart(self, birth_date: datetime, lat: float, lon: float):

        jd = self._get_date_to_jd(birth_date)

        # ================= PLANETS =================
        planet_data = {}

        for name, pid in self.planets.items():
            result = swe.calc_ut(jd, pid)
            lon_val = self._extract_lon(result)

            planet_data[name] = self._format_position(lon_val)

        # ================= NODES =================
        nodes_result = swe.calc_ut(jd, swe.TRUE_NODE)
        nodes = self._extract_lon(nodes_result)

        planet_data["Noeud Nord"] = self._format_position(nodes)
        planet_data["Noeud Sud"] = self._format_position((nodes + 180) % 360)

        # ================= HOUSES =================
        houses, ascmc = swe.houses(jd, lat, lon, b'P')

        houses_data = {
            i + 1: {
                "lon": float(h),
                "sign": self._get_sign(h),
                "deg": round(float(h) % 30, 2)
            }
            for i, h in enumerate(houses)
        }

        ascendant = self._format_position(ascmc[0])

        # ================= ASPECTS =================
        aspects = self._calculate_aspects(planet_data)

        # ================= TRANSITS =================
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

