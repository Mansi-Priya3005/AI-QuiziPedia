from llm_quiz_generator import QuizGenerator
from scraper import scrape_wikipedia

url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
text, title = scrape_wikipedia(url)
generator = QuizGenerator()
quiz = generator.generate_quiz(text)
print(quiz)