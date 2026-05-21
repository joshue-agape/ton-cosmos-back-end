import re
import json
import logging
import anthropic
from app.core.config import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

        
    async def GenerateSVGMap(self, chart: dict): 
        prompt = f"""
        Génère le code source SVG d'une carte du ciel astrologique minimaliste mais optimisée pour une couverture de livre.

        DONNÉES ASTRALES À REPRÉSENTER : {chart}

        RÈGLES DE DESIGN (ZÉRO TEXTE) :
        1. SYMBOLES ET COORDONNÉES INCLUS : Intègre les symboles (glyphes) des planètes, les signes du zodiaque et les lignes des maisons/degrés.
        2. ZÉRO LÉGENDE : Aucun texte explicatif, aucun nom en toutes lettres, aucun tableau. Uniquement du graphisme.
        3. ESTHÉTIQUE : Épuré, lignes fines (stroke-width="1").

        RÈGLES D'OPTIMISATION STRICTES (POUR ÉCONOMISER LES TOKENS) :
        - CODE COMPACT : Factorise au maximum. Utilise une balise `<style>` globale au début au lieu de répéter `stroke="..."` et `fill="..."` sur chaque ligne.
        - GLYPHES RÉUTILISABLES : Déclare les symboles complexes une seule fois dans des balises `<defs>` et réutilise-les avec `<use href="#id" x="..." y="..." />`.
        - PAS DE COMMENTAIRES, pas d'indentation excessive, pas de sauts de ligne inutiles. Reste ultra-concis.

        RÈGLES TECHNIQUES CRITIQUES :
        - Réponds UNIQUEMENT avec le code source SVG brut, sans blabla ni explications avant/après.
        - INTERDICTION ABSOLUE d'utiliser les blocs Markdown (PAS de ```svg ou ```). Commence directement par <svg> et finis par </svg>.
        - Dimensions : viewBox="0 0 500 500" width="100%" height="100%".
        
        IMPORTANT : Ton quota est de 5000 tokens, mais tu dois rester concis et structuré pour ne jamais tronquer la fermeture du SVG. Finis impérativement par '</svg>'.
        """
        
        raw_content = ""
        
        try:
            response = await self.client.messages.create(
                model="claude-opus-4-6", 
                max_tokens=8000,
                temperature=0,
                system="Tu es Indira. Ton unique but est de générer du code SVG valide. Ne salue pas. Ne commente pas.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_content = response.content[0].text.strip()

            svg_match = re.search(r'(<svg.*?</svg>)', raw_content, re.DOTALL | re.IGNORECASE)
            
            if svg_match:
                svg_code = svg_match.group(1)
            else:
                svg_code = raw_content.replace("```svg", "").replace("```", "").strip()

            if "<svg" not in svg_code.lower():
                logger.error(f"Contenu non-SVG reçu : {raw_content[:200]}")
                return '<svg width="500" height="500" xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)"></svg>'

            return svg_code
        
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON : {raw_content[:200]}")
            raise Exception("Format JSON invalide reçu de l'IA.")
        except Exception as e:
            logger.error(f"Erreur Claude : {e}")
            raise e


    async def generate_astrology_report(self, chart: dict, full_name: str, section_key: str) -> Dict[str, Any]:
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
        2. Développe chaque paragraphe de manière très riche (environts 50 à 120 mots par paragraphe maximum).
        3. INTERDICTION FORMELLE d'utiliser des retours à la ligne réels (touches Entrée) à l'intérieur des valeurs de texte. Utilise exclusivement '\\n' pour simuler un saut de ligne si nécessaire.
        4. N'utilise pas de caractères spéciaux non standards ou de guillemets doubles (") à l'intérieur de tes textes (utilise des guillemets simples ' à la place).

        ### FORMAT DE SORTIE : 
        - Retourne UNIQUEMENT du JSON pur, pas de bonjour, pas de blablabla. 
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
                    "note": "Note courte" ou Null,
                    "conseil": "Conseil pratique" ou Null
                }}
            ],
            "summary": "Conclusion synthétique"
        }}

        IMPORTANT : Ton quota est de 5000 tokens, mais tu dois rester concis et structuré pour ne jamais tronquer la fermeture du JSON. Finis impérativement par '}}'.
        """
        
        raw_content = ""
        
        try:
            response = await self.client.messages.create(
                model="claude-opus-4-6", 
                max_tokens=8000,
                temperature=0.7,
                system="Tu es Indira. Réponds uniquement en JSON pur. Ne parle pas, ne salue pas, envoie juste le code.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_content = response.content[0].text.strip()
            
            if "```" in raw_content:
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
                raw_content = raw_content.strip()

            if not raw_content.endswith("}"):
                logger.warning(f"Réparation JSON pour {full_name}")
                if not raw_content.endswith('"') and not raw_content.endswith(']'):
                    raw_content += '"'
                if raw_content.count('[') > raw_content.count(']'):
                    raw_content += ']}'
                if raw_content.count('{') > raw_content.count('}'):
                    raw_content += '}'

            return json.loads(raw_content)

        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON : {raw_content[:200]}")
            raise Exception("Format JSON invalide reçu de l'IA.")
        except Exception as e:
            logger.error(f"Erreur Claude : {e}")
            raise e
        