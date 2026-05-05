import json
import anthropic
from app.core.config import settings

class AIService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        
    
    def test_claude_connection(self):
        test_schema = {
            "status": "ok",
            "message": "test",
            "sections": [{"title": "test", "blocks": [], "summary": "test"}]
        }
        
        try:
            response = self.client.messages.create(
                model="claude-opus-4-6", 
                max_tokens=200,
                temperature=0,
                system=f"Réponds uniquement par un JSON valide respectant cette structure: {json.dumps(test_schema)}",
                messages=[{"role": "user", "content": "Génère un JSON de test court."}]
            )
            
            raw_content = response.content[0].text.strip()
            
            if raw_content.startswith("```json"):
                raw_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            return json.loads(raw_content)
            
        except Exception as e:
            return {"error": str(e), "integration_status": "failed"}


    def generate_astrology_report(self, chart: dict, full_name: str, plan_type: str):
        is_complete = plan_type.lower() == "complete"
        
        response_schema = {
            "sections": [
                {
                    "id": "portrait",
                    "title": "Ton Essence Astrale",
                    "blocks": [
                        {"subtitle": "Le Soleil en...", "content": ["paragraphe 1", "paragraphe 2"]},
                        {"subtitle": "L'Ascendant...", "content": ["paragraphe 1"]}
                    ]
                }
            ]
        }
        
        prompt = f"""
### RÔLE
Tu es Indira, astrologue experte. Tu tutoies {full_name}.

### DONNÉES DU THÈME
{chart}

### OBJECTIF ET STRUCTURE
Génère un rapport astrologique ultra-détaillé au format JSON. 
Le JSON doit suivre strictement cette hiérarchie pour chaque section :
- 'title': Le titre de la section.
- 'blocks': Un tableau d'objets contenant :
    - 'subtitle': Le sous-titre (ex: l'aspect spécifique analysé).
    - 'paragraphs': Un tableau de chaînes de caractères (chaque chaîne = un paragraphe de 150 mots minimum).
- 'summary': Une conclusion synthétique pour la section.

### SECTIONS À GÉNÉRER
1. 'portrait': Portrait complet (Soleil, Lune, Ascendant, Dominantes).
2. 'amour': Relations (Vénus, Mars, Maison VII).
3. 'mission': Carrière et Destin (Maison X, Nœud Nord).
{ "4. 'ombres': Défis (Saturne, Maison XII). 5. 'predictions': Prévisions 12 mois." if is_complete else "4. 'conseils': Actions concrètes." }

### CONTRAINTES
- Retourne UNIQUEBLENT le JSON.
- Évite le jargon : explique l'impact psychologique des placements.
- Pour chaque bloc, cite obligatoirement le placement (ex: "Ta Lune en Verseau...").
"""

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            temperature=0.7,
            system=f"Tu es Indira. Réponds exclusivement en JSON pur respectant cette interface: {json.dumps(response_schema)}",
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw_content = response.content[0].text.strip()
        
        if raw_content.startswith("```json"):
            raw_content = raw_content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(raw_content)
    