import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
from models import QuizOutput

load_dotenv()

class QuizGenerator:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
    def generate_quiz(self, article_text: str) -> QuizOutput:
        """Generate quiz from article text using direct Gemini API"""
        
        prompt = f"""
        You are an expert educational content creator. Create a comprehensive quiz based on the following Wikipedia article content.
        
        ARTICLE CONTENT:
        {article_text[:8000]}  # Limit text length
        
        IMPORTANT INSTRUCTIONS:
        1. Generate 5-8 high-quality quiz questions that test understanding of key concepts
        2. Questions should be factual and directly based on the provided content
        3. Each question must have exactly 4 options labeled A, B, C, D
        4. Provide the correct answer as JUST THE LETTER (A, B, C, or D) - NOT the full text
        5. Assign appropriate difficulty levels (easy, medium, hard)
        6. Provide a brief explanation for each answer
        7. Extract key entities (people, organizations, locations)
        8. Identify main sections of the article
        9. Suggest 3-5 related Wikipedia topics for further reading
        
        CRITICAL: The "answer" field must contain ONLY the letter (A, B, C, or D), not the full option text.
        
        Return the response in this exact JSON format:
        {{
            "summary": "Concise summary of the article",
            "key_entities": {{
                "people": ["list", "of", "people"],
                "organizations": ["list", "of", "organizations"], 
                "locations": ["list", "of", "locations"]
            }},
            "sections": ["list", "of", "main", "sections"],
            "quiz": [
                {{
                    "question": "Question text?",
                    "options": [
                        "A) Option A text",
                        "B) Option B text", 
                        "C) Option C text",
                        "D) Option D text"
                    ],
                    "answer": "A",  # MUST BE JUST THE LETTER A, B, C, or D
                    "difficulty": "easy",
                    "explanation": "Brief explanation of why this is correct"
                }}
            ],
            "related_topics": ["topic1", "topic2", "topic3"]
        }}
        
        Make sure the response is valid JSON that can be parsed directly.
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'\s*```', '', response_text)
            response_text = response_text.strip()
            
            quiz_data = json.loads(response_text)
            
            for question in quiz_data.get('quiz', []):
                if 'answer' in question:
                    answer = str(question['answer']).strip().upper()
                    if len(answer) == 1 and answer in ['A', 'B', 'C', 'D']:
                        question['answer'] = answer
                    else:
                        match = re.match(r'^([A-D])', answer)
                        if match:
                            question['answer'] = match.group(1)
                        else:
                            question['answer'] = 'A'
            
            return QuizOutput(**quiz_data)
            
        except Exception as e:
            print(f"Quiz generation error: {e}")
            return self._get_fallback_quiz()
    
    def _get_fallback_quiz(self) -> QuizOutput:
        """Return a fallback quiz when generation fails"""
        return QuizOutput(
            summary="Failed to generate summary due to API error",
            key_entities={
                "people": [],
                "organizations": [], 
                "locations": []
            },
            sections=[],
            quiz=[
                {
                    "question": "What is the main topic of this article?",
                    "options": [
                        "A) The content is not available",
                        "B) Please try generating the quiz again", 
                        "C) There was an error processing the article",
                        "D) The AI service is temporarily unavailable"
                    ],
                    "answer": "B",
                    "difficulty": "easy",
                    "explanation": "There was an issue generating the quiz. Please try again."
                }
            ],
            related_topics=[]
        )