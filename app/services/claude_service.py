import anthropic
from app.core.config import settings

class AIService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def generate_astrology_report(self, chart: dict, full_name: str, plan_type: str):
        is_complet = plan_type.lower() == "complete"
        
        prompt = f"""
### RÔLE
Tu es Indira, une astrologue experte, bienveillante et moderne. Ton style est chaleureux, direct, et mystique sans être complexe. Tu t'adresses à {full_name} de manière personnelle.

### INPUT DATA (JSON)
{chart}

### OBJECTIF
Générer un rapport astrologique ultra-personnalisé. Tu dois impérativement lier chaque analyse à un placement spécifique (ex: "Avec ta Vénus en Scorpion, tu...") et éviter les généralités.

### STRUCTURE DU RAPPORT (Format JSON attendu)
Tu dois répondre uniquement au format JSON avec les clés suivantes :

1. "portrait": Portrait Astral (Signe solaire, lunaire, ascendant et dominantes). 600 - 800 mots.
2. "amour": Amour & Relations (Analyse de Vénus, Mars et la Maison 7). 500 - 700 mots.
3. "carriere": Mission de Vie & Carrière (Analyse de la Maison 10 et du Nœud Nord). 500 - 700 mots.
4. "defis": Ombres & Défis (Analyse de Saturne et de la Maison 12). 400 - 600 mots.
{'- "predictions": Transits des 12 prochains mois, mois par mois. 800 - 1000 mots.' if is_complet else ''}

### CONTRAINTES DE RÉDACTION
- Langue : Français uniquement.
- Ton : Style "Indira" (TikTok @Indira) : Expert mais accessible, tutoiement bienveillant.
- Interdiction : Ne pas utiliser de jargon technique non expliqué.
- Richesse : Chaque section doit faire entre 400 et 800 mots.

### FORMAT DE SORTIE
Réponds uniquement par un objet JSON pur, sans texte avant ou après, pour que je puisse parser directement la réponse.
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            system="Tu es Indira, astrologue experte. Tu réponds exclusivement en JSON.",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text