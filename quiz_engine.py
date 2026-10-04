import asyncio

from config import QUIZ_TIME_LIMIT
from questions import get_question_for_user


class QuizEngine:
	def __init__(self, store):
		self.store = store
		self.active_quiz = None
		self.timer_task = None

	def cancel_timer(self):
		if self.timer_task is not None:
			self.timer_task.cancel()
			self.timer_task = None

	async def get_question(self, guild_id, user_id, settings):
		return await get_question_for_user(
			self.store,
			guild_id,
			user_id,
			settings,
		)

	def set_active_quiz(self, guild_id, user_id, channel, question):
		self.active_quiz = {
			"question": question,
			"channel": channel,
			"user_id": user_id,
			"guild_id": guild_id,
		}

	def start_timer(self):
		self.timer_task = asyncio.create_task(self._quiz_timeout(self.active_quiz))

	async def _quiz_timeout(self, quiz_data):
		await asyncio.sleep(QUIZ_TIME_LIMIT)
		if self.active_quiz is not quiz_data:
			return

		self.active_quiz = None
		self.timer_task = None
		player = self.store.get_player(quiz_data["guild_id"], quiz_data["user_id"])
		player["streak"] = 0
		self.store.save()
		question = quiz_data["question"]
		await quiz_data["channel"].send(
			f"⏰ Time's up! The correct answer was "
			f"{question['correct_answer']}) {question['correct_answer_text']}."
		)

	async def handle_answer(self, message):
		if message.author.bot or message.guild is None:
			return None

		answer = message.content.strip().upper()
		if self.active_quiz is None or answer not in {"A", "B", "C", "D"}:
			return None

		quiz_data = self.active_quiz
		question = quiz_data["question"]
		correct_answer = question["correct_answer"]
		correct_answer_text = question["correct_answer_text"]
		self.active_quiz = None
		self.cancel_timer()

		player = self.store.get_player(message.guild.id, message.author.id)
		if answer == correct_answer:
			player["display_name"] = message.author.display_name
			self.store.add_player_xp(message.guild.id, message.author.id, 10)
			player["streak"] += 1
			self.store.save()
			if player["streak"] > 1:
				return f"✅ Correct! +10 XP 🔥 {player['streak']} answer streak!"
			return "✅ Correct! +10 XP"

		player["streak"] = 0
		self.store.save()
		return (
			f"❌ Wrong! The correct answer was {correct_answer}) "
			f"{correct_answer_text}. Streak reset."
		)
