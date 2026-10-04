import asyncio
import hashlib
import html
import json
import random
import urllib.error
import urllib.request
from urllib.parse import unquote, urlencode

from config import CATEGORY_API_IDS, TRIVIA_API_URL


questions = [
	{
		"question": "What is the capital of Japan?",
		"options": {"A": "Seoul", "B": "Tokyo", "C": "Beijing", "D": "Bangkok"},
		"correct_answer": "B",
		"correct_answer_text": "Tokyo",
	},
	{
		"question": "Which planet is known as the Red Planet?",
		"options": {"A": "Venus", "B": "Jupiter", "C": "Mars", "D": "Saturn"},
		"correct_answer": "C",
		"correct_answer_text": "Mars",
	},
	{
		"question": "What is 5 x 6?",
		"options": {"A": "25", "B": "30", "C": "35", "D": "40"},
		"correct_answer": "B",
		"correct_answer_text": "30",
	},
	{
		"question": "Who wrote Romeo and Juliet?",
		"options": {"A": "William Shakespeare", "B": "Mark Twain", "C": "Jane Austen", "D": "Charles Dickens"},
		"correct_answer": "A",
		"correct_answer_text": "William Shakespeare",
	},
	{
		"question": "Which ocean is the largest?",
		"options": {"A": "Atlantic Ocean", "B": "Indian Ocean", "C": "Arctic Ocean", "D": "Pacific Ocean"},
		"correct_answer": "D",
		"correct_answer_text": "Pacific Ocean",
	},
	{
		"question": "What gas do plants absorb from the atmosphere?",
		"options": {"A": "Oxygen", "B": "Nitrogen", "C": "Carbon dioxide", "D": "Hydrogen"},
		"correct_answer": "C",
		"correct_answer_text": "Carbon dioxide",
	},
	{
		"question": "How many sides does a hexagon have?",
		"options": {"A": "Five", "B": "Six", "C": "Seven", "D": "Eight"},
		"correct_answer": "B",
		"correct_answer_text": "Six",
	},
	{
		"question": "Which animal is known as the King of the Jungle?",
		"options": {"A": "Tiger", "B": "Elephant", "C": "Lion", "D": "Leopard"},
		"correct_answer": "C",
		"correct_answer_text": "Lion",
	},
	{
		"question": "What is the boiling point of water at sea level in Celsius?",
		"options": {"A": "90 degrees", "B": "100 degrees", "C": "110 degrees", "D": "120 degrees"},
		"correct_answer": "B",
		"correct_answer_text": "100 degrees",
	},
	{
		"question": "Which language is primarily used to style web pages?",
		"options": {"A": "HTML", "B": "Python", "C": "CSS", "D": "SQL"},
		"correct_answer": "C",
		"correct_answer_text": "CSS",
	},
]


def decode_trivia_text(text):
	return html.unescape(unquote(text))


def fetch_trivia_question(recent_question_ids, category, difficulty):
	try:
		parameters = {
			"amount": 1,
			"type": "multiple",
			"encode": "url3986",
			"category": CATEGORY_API_IDS[category],
		}
		if difficulty != "any":
			parameters["difficulty"] = difficulty
		url = f"{TRIVIA_API_URL}?{urlencode(parameters)}"
		request = urllib.request.Request(
			url,
			headers={"User-Agent": "KnightQuiz/1.0"},
		)
		with urllib.request.urlopen(request, timeout=5) as response:
			data = json.loads(response.read().decode("utf-8"))

		if not isinstance(data, dict) or data.get("response_code") != 0:
			return None
		results = data.get("results")
		if not isinstance(results, list) or not results:
			return None
		result = results[0]
		if not isinstance(result, dict):
			return None
		encoded_answers = result.get("incorrect_answers", [])
		encoded_correct_answer = result.get("correct_answer")
		encoded_question = result.get("question")
		if len(encoded_answers) != 3 or not encoded_correct_answer or not encoded_question:
			return None

		question_text = decode_trivia_text(encoded_question)
		correct_answer_text = decode_trivia_text(encoded_correct_answer)
		answers = [
			(decode_trivia_text(answer), False) for answer in encoded_answers
		]
		answers.append((correct_answer_text, True))
		question_id = "trivia:" + hashlib.sha256(
			question_text.encode("utf-8")
		).hexdigest()
		if question_id in recent_question_ids:
			return None

		random.shuffle(answers)
		options = {}
		correct_answer = None
		for position, (answer, is_correct) in enumerate(answers):
			letter = chr(ord("A") + position)
			options[letter] = answer
			if is_correct:
				correct_answer = letter

		return {
			"id": question_id,
			"question": question_text,
			"options": options,
			"correct_answer": correct_answer,
			"correct_answer_text": correct_answer_text,
		}
	except (
		urllib.error.URLError,
		TimeoutError,
		json.JSONDecodeError,
		KeyError,
		IndexError,
		TypeError,
		AttributeError,
		UnicodeDecodeError,
		OSError,
	):
		return None


def get_local_question(store, guild_id, user_id):
	player = store.get_player(guild_id, user_id)
	seen_question_ids = player["seen_questions"]
	all_question_ids = list(range(len(questions)))
	unseen_question_ids = [
		question_id
		for question_id in all_question_ids
		if question_id not in seen_question_ids
	]
	if not unseen_question_ids:
		seen_question_ids.clear()
		unseen_question_ids = all_question_ids

	question_id = random.choice(unseen_question_ids)
	seen_question_ids.append(question_id)
	question = questions[question_id].copy()
	question["id"] = question_id
	return question


async def get_question_for_user(store, guild_id, user_id, settings):
	player = store.get_player(guild_id, user_id)
	recent_question_ids = player["recent_question_ids"]
	for _ in range(3):
		trivia_question = await asyncio.to_thread(
			fetch_trivia_question,
			recent_question_ids,
			settings["category"],
			settings["difficulty"],
		)
		if trivia_question is not None:
			recent_question_ids.append(trivia_question["id"])
			recent_question_ids[:] = recent_question_ids[-20:]
			return trivia_question

	return get_local_question(store, guild_id, user_id)
