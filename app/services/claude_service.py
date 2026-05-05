import json
import logging
import anthropic
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        
    
    def test_claude_connection(self):
        try:
            response = self.client.messages.create(
                model="claude-opus-4-6", 
                max_tokens=200,
                temperature=0,
                system=f"Réponds uniquement par un JSON valide",
                messages=[{"role": "user", "content": "Génère un JSON."}]
            )
            
            raw_content = response.content[0].text.strip()
            
            if raw_content.startswith("```json"):
                raw_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            return json.loads(raw_content)
            
        except Exception as e:
            return {"error": str(e), "integration_status": "failed"}


    def generate_astrology_report(self, chart: dict, full_name: str, section_key: str):
        section_prompts = {
            "introduction": "Voyage au cœur de ton ciel : Une introduction immersive à l'astrologie comme outil de connaissance de soi et le message d'Indira pour ton évolution.",
            "piliers": "Les Fondations de l'Être : Analyse psychologique croisée et approfondie de ton 'Big Three' (Soleil, Lune, Ascendant). Comment ton essence, tes besoins émotionnels et ton masque social s'unissent.",
            "mental": "L'Alchimie de la Pensée : Étude détaillée de ton Mercure. Ta manière de traiter l'information, ton style de communication, tes apprentissages et ton fonctionnement intellectuel.",
            "dominantes": "Ta Signature Énergétique : Analyse de tes forces dominantes, de la répartition des éléments (Feu, Terre, Air, Eau) et des modes (Cardinal, Fixe, Mutable) qui régissent ton tempérament.",
            "maisons_vie_1": "La Roue du Destin (Partie I) : Exploration profonde des 6 premiers secteurs de vie. Ton identité (I), tes ressources (II), ton mental (III), tes racines (IV), ta créativité (V) et ton quotidien (VI).",
            "maisons_vie_2": "La Roue du Destin (Partie II) : Exploration des 6 secteurs relationnels et spirituels. Tes partenariats (VII), tes transformations (VIII), ta quête de sens (IX), ton destin social (X), tes projets (XI) et tes mystères (XII).",
            "amour": "Le Langage du Cœur : Analyse de Vénus, de Mars et de la Maison VII. Tes besoins affectifs, ta façon de séduire, d'aimer et ta dynamique de désir au sein du couple.",
            "mission": "L'Appel du Monde : Analyse de ta vocation et de ta réussite via le Milieu du Ciel (Maison X), Saturne (tes responsabilités) et la Maison VI (ton service au quotidien).",
            "destin": "La Boussole de l'Âme : Étude karmique et évolutive des Nœuds Lunaires (Nord et Sud) et de ta Part de Fortune pour comprendre ton chemin de croissance.",
            "ombres": "L'Espace de Guérison : Exploration des points sensibles. Ta blessure sacrée avec Chiron, tes désirs inconscients avec la Lune Noire et les héritages du passé.",
            "aspects_majeurs": "Le Dialogue des Astres : Analyse complexe des interactions géométriques majeures (Carrés, Trines, Oppositions). Tes défis intérieurs et tes dons innés.",
            "predictions": "Les Cycles à Venir : Analyse prospective détaillée des transits planétaires majeurs pour les 12 prochains mois et les opportunités de transformation à saisir.",
            "conseils": "Rituels et Harmonie : Actions concrètes, pratiques d'alignement et conseils holistiques pour incarner pleinement les énergies de ton thème.",
            "synthese": "L'Unité Retrouvée : Synthèse magistrale de ton ciel, message final de sagesse d'Indira et perspectives pour ton futur glorieux."
        }
        
        prompt = f"""
        ### RÔLE : Indira, astrologue experte. Tu tutoies {full_name}.
        ### DONNÉES DU THÈME : {chart}
        ### TÂCHE : Génère EXCLUSIVEMENT la section '{section_key}' : {section_prompts.get(section_key)}
        ### STYLE : Chaleureux, profond, sans jargon technique complexe.

        ### CONTRAINTES DE RÉDACTION (STRICTES) :
        1. Pour chaque bloc, cite le placement (ex: "Ta Lune en Verseau...").
        2. Développe chaque paragraphe de manière très riche (environts 150 mots par paragraphe).
        3. INTERDICTION FORMELLE d'utiliser des retours à la ligne réels (touches Entrée) à l'intérieur des valeurs de texte. Utilise exclusivement '\\n' pour simuler un saut de ligne si nécessaire.
        4. N'utilise pas de caractères spéciaux non standards ou de guillemets doubles (") à l'intérieur de tes textes (utilise des guillemets simples ' à la place).

        ### FORMAT DE SORTIE : 
        - Retourne UNIQUEMENT du JSON pur. 
        - Pas de balises markdown (pas de ```json).
        - Pas de texte avant ou après le bloc JSON.

        ### STRUCTURE JSON :
        {{
            "id": "{section_key}",
            "title": "Titre créatif court",
            "blocks": [
                {{ 
                    "subtitle": "Sous-titre sans saut de ligne", 
                    "paragraphs": [
                        "Texte du premier paragraphe sans retour à la ligne réel.",
                        "Texte du second paragraphe sans retour à la ligne réel."
                    ],
                    "note": "Note courte",
                    "conseil": "Conseil pratique"
                }}
            ],
            "summary": "Conclusion synthétique"
        }}

        IMPORTANT : Ton quota est de 5000 tokens, mais tu dois rester concis et structuré pour ne jamais tronquer la fermeture du JSON. Finis impérativement par '}}'.
        """
        
        raw_content = ""
        
        try:
            response = self.client.messages.create(
                model="claude-opus-4-6", 
                max_tokens=8000,
                temperature=0.7,
                system="Tu es Indira. Réponds uniquement en JSON pur. Ne parle pas, ne salue pas, envoie juste le code.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_content = response.content[0].text.strip()
            
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()

            if not raw_content.endswith("}"):
                logger.warning(f"JSON tronqué détecté pour l'ordre de {full_name}. Tentative de réparation...")
                if not raw_content.endswith('"') and not raw_content.endswith(']'):
                    raw_content += '"'
                
                if ']' in raw_content and '}' not in raw_content:
                    raw_content += '}'
                elif ']' not in raw_content:
                    raw_content += ']}' if raw_content.count('{') > raw_content.count('}') else ""
                    
                if raw_content.count('{') > raw_content.count('}'):
                    raw_content += '}'

            return json.loads(raw_content)

        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON. Contenu partiel : {raw_content[:200]}")
            raise Exception(f"Le format de réponse de l'IA est invalide : {str(e)}")
        except Exception as e:
            logger.error(f"Erreur critique lors de la génération Claude : {str(e)}")
            raise e
        