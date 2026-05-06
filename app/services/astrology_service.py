import asyncio
import swisseph as swe
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor


class AstrologyService:
    def __init__(self):
        swe.set_ephe_path('/usr/share/ephe')
        
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.planets_map = {
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
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_dt = dt.astimezone(timezone.utc)
        
        return swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day, 
            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
        )
    
    
    def _extract_lon(self, result):
        if isinstance(result, (list, tuple)):
            if isinstance(result[0], (list, tuple)):
                return float(result[0][0])
            return float(result[0])
        return float(result)
    
    
    def _get_sign(self, lon: float) -> str:
        return self.signs[int((lon % 360) // 30)]
    
    
    def _format_position(self, lon: float) -> Dict[str, Any]:
        lon = lon % 360
        return {
            "lon": round(lon, 4),
            "sign": self._get_sign(lon),
            "deg": round(lon % 30, 2)
        }


    def _calculate_aspects_sync(self, planets: Dict[str, Any]) -> List[Dict[str, Any]]:
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


    def _run_heavy_calculation(self, birth_date: datetime, lat: float, lon: float) -> Dict[str, Any]:
        jd = self._get_date_to_jd(birth_date)
        planet_data = {}

        for name, pid in self.planets_map.items():
            res = swe.calc_ut(jd, pid)
            planet_data[name] = self._format_position(self._extract_lon(res))

        nodes_res = swe.calc_ut(jd, swe.TRUE_NODE)
        n_nord_lon = self._extract_lon(nodes_res)
        planet_data["Noeud Nord"] = self._format_position(n_nord_lon)
        planet_data["Noeud Sud"] = self._format_position((n_nord_lon + 180) % 360)

        houses, ascmc = swe.houses(jd, lat, lon, b'P')
        
        houses_data = {
            i + 1: {
                "lon": float(h),
                "sign": self._get_sign(h),
                "deg": round(float(h) % 30, 2)
            } for i, h in enumerate(houses)
        }
        
        ascendant = self._format_position(ascmc[0])

        aspects = self._calculate_aspects_sync(planet_data)

        forecast = []
        slow_planets = {"Jupiter": swe.JUPITER, "Saturne": swe.SATURN, "Pluton": swe.PLUTO}
        
        for i in range(1, 13):
            future_jd = jd + (i * 30)
            pos_at_date = {}
            for name, pid in slow_planets.items():
                res = swe.calc_ut(future_jd, pid)
                pos_at_date[name] = self._get_sign(self._extract_lon(res))
            
            forecast.append({
                "period": f"+{i} mois",
                "positions": pos_at_date
            })

        return {
            "birth_chart": {
                "planets": planet_data,
                "ascendant": ascendant,
                "houses": houses_data,
                "aspects": aspects
            },
            "forecast": forecast
        }


    async def get_full_chart(self, birth_date: datetime, lat: float, lon: float) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._run_heavy_calculation, 
            birth_date, lat, lon
        )
