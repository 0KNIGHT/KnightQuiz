import asyncio
from datetime import datetime, timezone
import hashlib
import html
import json
import os
import random
import urllib.error
import urllib.request
from urllib.parse import unquote, urlencode

import discord
from discord import app_commands
from dotenv import load_dotenv


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
TRIVIA_API_URL = "https://opentdb.com/api.php"
DEVELOPMENT_GUILD_ID = "1504712089535774820"
CATEGORY_API_IDS = {
	"general": 9,
	"gaming": 15,
	"anime": 31,
	"football": 21,
	"cricket": 21,
	"technology": 18,
}
CATEGORY_LABELS = {
	"general": "General Knowledge",
	"gaming": "Gaming",
	"anime": "Anime & Manga",
	"football": "Football",
	"cricket": "Cricket",
	"technology": "Technology",
}
DIFFICULTIES = {"any", "easy", "medium", "hard"}
CATEGORY_CHOICES = [
	app_commands.Choice(name=label, value=value)
	for value, label in CATEGORY_LABELS.items()
]
DIFFICULTY_CHOICES = [
	app_commands.Choice(name="Easy", value="easy"),
	app_commands.Choice(name="Medium", value="medium"),
	app_commands.Choice(name="Hard", value="hard"),
	app_commands.Choice(name="Any", value="any"),
]
LEADERBOARD_CHOICES = [
	app_commands.Choice(name="Daily", value="daily"),
	app_commands.Choice(name="Lifetime", value="lifetime"),
]


def empty_player(user_id):
	return {
		"xp": 0,
		"daily_xp": 0,
		"streak": 0,
		"display_name": str(user_id),
		"seen_questions": [],
		"recent_question_ids": [],
	}


def load_data():
	try:
		with open(DATA_FILE, "r", encoding="utf-8") as file:
			data = json.load(file)
	except (FileNotFoundError, json.JSONDecodeError, OSError):
		return {"players": {}, "servers": {}}

	if not isinstance(data, dict):
		return {"players": {}, "servers": {}}

	if isinstance(data.get("players"), dict):
		raw_players = data["players"]
	elif "servers" not in data:
		raw_players = data
	else:
		raw_players = {}
	if raw_players and all(
		isinstance(player, dict) and "xp" in player
		for player in raw_players.values()
	):
		raw_players = {DEVELOPMENT_GUILD_ID: raw_players}
	raw_servers = data.get("servers", {})
	if not isinstance(raw_servers, dict):
		raw_servers = {}

	valid_players = {}
	for guild_id, players in raw_players.items():
		if not isinstance(guild_id, str) or not guild_id.isdigit() or not isinstance(players, dict):
			continue
		valid_players[guild_id] = {}
		for user_id, player in players.items():
			if not isinstance(user_id, str) or not isinstance(player, dict):
				continue

			try:
				int(user_id)
			except ValueError:
				continue

			xp = player.get("xp", 0)
			daily_xp = player.get("daily_xp", 0)
			streak = player.get("streak", 0)
			if not isinstance(xp, int) or xp < 0:
				xp = 0
			if not isinstance(daily_xp, int) or daily_xp < 0:
				daily_xp = 0
			if not isinstance(streak, int) or streak < 0:
				streak = 0
			seen_questions = player.get("seen_questions", [])
			if not isinstance(seen_questions, list):
				seen_questions = []
			recent_question_ids = player.get("recent_question_ids", [])
			if not isinstance(recent_question_ids, list):
				recent_question_ids = []

			player_data = dict(player)
			player_data.update({
				"xp": xp,
				"daily_xp": daily_xp,
				"streak": streak,
				"display_name": player.get("display_name", user_id),
				"seen_questions": [
					question_id
					for question_id in seen_questions
					if isinstance(question_id, int) and not isinstance(question_id, bool)
				],
				"recent_question_ids": [
					question_id
					for question_id in recent_question_ids
					if isinstance(question_id, str)
				],
			})
			valid_players[guild_id][user_id] = player_data

	valid_servers = {}
	for guild_id, settings in raw_servers.items():
		if not isinstance(guild_id, str) or not guild_id.isdigit() or not isinstance(settings, dict):
			continue
		category = settings.get("category", "general")
		difficulty = settings.get("difficulty", "any")
		if category not in CATEGORY_API_IDS:
			category = "general"
		if difficulty not in DIFFICULTIES:
			difficulty = "any"
		valid_servers[guild_id] = {
			"category": category,
			"difficulty": difficulty,
		}

	reset_date = data.get("daily_reset_date")
	if not isinstance(reset_date, str):
		reset_date = None
	return {
		"players": valid_players,
		"servers": valid_servers,
		"daily_reset_date": reset_date,
	}


def save_data():
	data = {
		"players": player_data,
		"servers": server_settings,
		"daily_reset_date": daily_reset_date,
	}

	with open(DATA_FILE, "w", encoding="utf-8") as file:
		json.dump(data, file, indent=4)




saved_data = load_data()
player_data = saved_data["players"]
server_settings = saved_data["servers"]
daily_reset_date = saved_data["daily_reset_date"]


intents = discord.Intents.default()
intents.message_content = True
active_quiz = None
quiz_timer_task = None

def current_utc_date():
	return datetime.now(timezone.utc).date().isoformat()


def reset_daily_period_if_needed():
	global daily_reset_date

	today = current_utc_date()
	if daily_reset_date == today:
		return

	for players in player_data.values():
		for player in players.values():
			player["daily_xp"] = 0
	daily_reset_date = today
	save_data()


def get_server_players(guild_id):
	return player_data.setdefault(str(guild_id), {})


def get_player(guild_id, user_id):
	players = get_server_players(guild_id)
	user_key = str(user_id)
	if user_key not in players:
		players[user_key] = empty_player(user_id)
	return players[user_key]


def add_player_xp(guild_id, user_id, amount):
	player = get_player(guild_id, user_id)
	player["xp"] += amount
	player["daily_xp"] += amount
	return player


def get_leaderboard(guild_id, leaderboard_type):
	players = get_server_players(guild_id)
	xp_key = "daily_xp" if leaderboard_type == "daily" else "xp"
	return sorted(
		players.items(),
		key=lambda item: item[1].get(xp_key, 0),
		reverse=True,
	)[:10]


reset_daily_period_if_needed()

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


def get_server_settings(guild_id):
	return server_settings.get(
		str(guild_id),
		{"category": "general", "difficulty": "any"},
	)


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


def get_local_question(guild_id, user_id):
	player = get_player(guild_id, user_id)
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


async def get_question_for_user(guild_id, user_id, settings):
	player = get_player(guild_id, user_id)
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

	return get_local_question(guild_id, user_id)


class QuizClient(discord.Client):
	def __init__(self, *, intents):
		super().__init__(intents=intents)
		self.tree = app_commands.CommandTree(self)


client = QuizClient(intents=intents)


async def quiz_timeout(quiz_data):
	global active_quiz, quiz_timer_task

	await asyncio.sleep(20)

	if active_quiz is not quiz_data:
		return

	active_quiz = None
	quiz_timer_task = None
	player = get_player(quiz_data["guild_id"], quiz_data["user_id"])
	player["streak"] = 0
	save_data()
	question = quiz_data["question"]
	await quiz_data["channel"].send(
		f"⏰ Time's up! The correct answer was "
		f"{question['correct_answer']}) {question['correct_answer_text']}."
	)


@client.tree.command(name="quiz", description="Start a quiz")
async def quiz(interaction: discord.Interaction):
	global active_quiz, quiz_timer_task

	if quiz_timer_task is not None:
		quiz_timer_task.cancel()

	reset_daily_period_if_needed()
	guild_id = interaction.guild_id or 0
	user_id = interaction.user.id
	active_quiz = None
	settings = get_server_settings(guild_id)
	question = await get_question_for_user(guild_id, user_id, settings)
	save_data()
	active_quiz = {
		"question": question,
		"channel": interaction.channel,
		"user_id": user_id,
	}
	options = question["options"]

	await interaction.response.send_message(
		f"🎯 Quiz time! {question['question']}\n"
		f"A) {options['A']}\n"
		f"B) {options['B']}\n"
		f"C) {options['C']}\n"
		f"D) {options['D']}"
	)
	quiz_timer_task = asyncio.create_task(quiz_timeout(active_quiz))


@client.tree.command(name="quiz-settings", description="Configure this server's quiz settings")
@app_commands.describe(
	category="The category to use for new quizzes",
	difficulty="The difficulty to use for new quizzes",
)
@app_commands.choices(category=CATEGORY_CHOICES, difficulty=DIFFICULTY_CHOICES)
async def quiz_settings(
	interaction: discord.Interaction,
	category: str | None = None,
	difficulty: str | None = None,
):
	if interaction.guild is None:
		await interaction.response.send_message(
			"Quiz settings can only be changed inside a server."
		)
		return

	permissions = interaction.user.guild_permissions
	if not (permissions.manage_guild or permissions.administrator):
		await interaction.response.send_message(
			"You need Manage Server or Administrator permission to change quiz settings."
		)
		return

	guild_id = str(interaction.guild.id)
	settings = get_server_settings(interaction.guild.id).copy()
	if category is None and difficulty is None:
		await interaction.response.send_message(
			f"Current quiz settings: category = "
			f"{CATEGORY_LABELS[settings['category']]}, "
			f"difficulty = {settings['difficulty'].title()}."
		)
		return

	if category is not None:
		settings["category"] = category
	if difficulty is not None:
		settings["difficulty"] = difficulty
	server_settings[guild_id] = settings
	save_data()
	await interaction.response.send_message(
		f"Quiz settings updated: category = "
		f"{CATEGORY_LABELS[settings['category']]}, "
		f"difficulty = {settings['difficulty'].title()}."
	)


@client.tree.command(name="leaderboard", description="Show the top quiz players")
@app_commands.describe(type="Which leaderboard to view")
@app_commands.choices(type=LEADERBOARD_CHOICES)
async def leaderboard(
	interaction: discord.Interaction,
	type: str,
):
	reset_daily_period_if_needed()
	if interaction.guild_id is None:
		await interaction.response.send_message(
			"The leaderboard can only be viewed inside a server."
		)
		return

	ranked_users = get_leaderboard(interaction.guild_id, type)
	if not ranked_users:
		await interaction.response.send_message("🏆 The leaderboard is empty.")
		return

	if type == "daily":
		leaderboard_text = ["🏆 KnightQuiz Daily Leaderboard"]
	else:
		leaderboard_text = ["🏆 KnightQuiz Lifetime Leaderboard"]
	medals = ["🥇", "🥈", "🥉"]

	for position, (user_id, player) in enumerate(ranked_users, start=1):
		medal = medals[position - 1] if position <= len(medals) else f"{position}."
		xp = player["daily_xp"] if type == "daily" else player["xp"]
		leaderboard_text.append(f"{medal} {player['display_name']} — {xp} XP")

	if type == "daily":
		leaderboard_text.append("\n⏰ Daily leaderboard resets at the next UTC day.")

	await interaction.response.send_message("\n".join(leaderboard_text))


@client.event
async def on_message(message: discord.Message):
	global active_quiz, quiz_timer_task

	if message.author.bot or message.guild is None:
		return
	reset_daily_period_if_needed()

	answer = message.content.strip().upper()
	if active_quiz is None or answer not in {"A", "B", "C", "D"}:
		return

	quiz_data = active_quiz
	question = quiz_data["question"]
	correct_answer = question["correct_answer"]
	correct_answer_text = question["correct_answer_text"]
	active_quiz = None
	if quiz_timer_task is not None:
		quiz_timer_task.cancel()
		quiz_timer_task = None

	if answer == correct_answer:
		user_id = message.author.id
		player = get_player(message.guild.id, user_id)
		player["display_name"] = message.author.display_name
		add_player_xp(message.guild.id, user_id, 10)
		player["streak"] += 1
		save_data()
		streak = player["streak"]
		if streak > 1:
			await message.channel.send(
				f"✅ Correct! +10 XP 🔥 {streak} answer streak!"
			)
		else:
			await message.channel.send("✅ Correct! +10 XP")
	else:
		player = get_player(message.guild.id, message.author.id)
		player["streak"] = 0
		save_data()
		await message.channel.send(
			f"❌ Wrong! The correct answer was {correct_answer}) "
			f"{correct_answer_text}. Streak reset."
		)


@client.event
async def on_ready():
	guild = discord.Object(id=1504712089535774820)
	await client.tree.sync()
	client.tree.clear_commands(guild=guild)
	client.tree.copy_global_to(guild=guild)
	synced_commands = await client.tree.sync(guild=guild)
	print(f"Synced {len(synced_commands)} commands to Knight Arena.")
	print("KnightQuiz is online!")


load_dotenv()
token = os.getenv("DISCORD_TOKEN")

if not token:
	raise RuntimeError("DISCORD_TOKEN environment variable is not set")

client.run(token)
