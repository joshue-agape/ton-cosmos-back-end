import anthropic
from app.core.config import settings

class AIService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def generate_astrology_report(self, chart: dict, full_name: str, plan_type: str):
        is_complete = plan_type.lower() == "complete"
        
        prompt = f"""
### RÔLE
Tu es Indira, une astrologue experte, bienveillante et moderne (ton chaleureux, direct, tutoiement). 
Tu t'adresses à {full_name} pour décrypter son cosmos.

### DONNÉES DU THÈME (JSON)
{chart}

### OBJECTIF
Générer un rapport ultra-personnalisé. Chaque paragraphe doit obligatoirement citer un placement spécifique (ex: "Ta Vénus en Maison VII...") pour éviter les généralités.

### STRUCTURE DU RAPPORT (Format JSON)
Tu dois répondre uniquement avec un objet JSON contenant les clés suivantes selon la formule choisie :

1. "portrait": Portrait Astral Complet (Soleil, Lune, Ascendant, Dominantes). [800 mots]
2. "amour": Analyse Amour et Relations (Vénus, Mars, Maison VII). [600 mots]
3. "mission": Mission de vie, Carrière et Finances (Maison X, Nœud Nord). [700 mots]
4. "conseils": Conseils personnalisés et actions concrètes. [400 mots]

{'''
5. "ombres": Ombres et défis personnels (Saturne, Maison XII). [500 mots]
6. "predictions": Prédictions mois par mois pour les 12 prochains mois (Transits). [1000 mots]
''' if is_complete else ''}

### CONTRAINTES DE RÉDACTION
- Langue : Français uniquement.
- Style : Fluide, premium, mystique mais sans jargon technique complexe[cite: 1].
- Longueur : {"Le rapport doit être très détaillé pour atteindre 40-60 pages une fois mis en page" if is_complete else "Le rapport doit être complet pour atteindre environ 30 pages"}.
- Format : Retourne uniquement le JSON pur, sans texte avant ou après.
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            system="Tu es Indira, astrologue experte. Tu réponds exclusivement en JSON.",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text