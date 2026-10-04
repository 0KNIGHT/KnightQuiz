import json
from datetime import datetime, timezone

from config import CATEGORY_API_IDS, DATA_FILE, DEVELOPMENT_GUILD_ID, DIFFICULTIES


class DataStore:
	def __init__(self):
		data = self.load_data()
		self.players = data["players"]
		self.servers = data["servers"]
		self.daily_reset_date = data["daily_reset_date"]

	@staticmethod
	def empty_player(user_id):
		return {
			"xp": 0,
			"daily_xp": 0,
			"streak": 0,
			"display_name": str(user_id),
			"seen_questions": [],
			"recent_question_ids": [],
		}

	@staticmethod
	def empty_data():
		return {"players": {}, "servers": {}, "daily_reset_date": None}

	def load_data(self):
		try:
			with open(DATA_FILE, "r", encoding="utf-8") as file:
				data = json.load(file)
		except (FileNotFoundError, json.JSONDecodeError, OSError):
			return self.empty_data()

		if not isinstance(data, dict):
			return self.empty_data()

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
			if (
				not isinstance(guild_id, str)
				or not guild_id.isdigit()
				or not isinstance(players, dict)
			):
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
						if isinstance(question_id, int)
						and not isinstance(question_id, bool)
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
			if (
				not isinstance(guild_id, str)
				or not guild_id.isdigit()
				or not isinstance(settings, dict)
			):
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

	def save(self):
		data = {
			"players": self.players,
			"servers": self.servers,
			"daily_reset_date": self.daily_reset_date,
		}
		with open(DATA_FILE, "w", encoding="utf-8") as file:
			json.dump(data, file, indent=4)

	@staticmethod
	def current_utc_date():
		return datetime.now(timezone.utc).date().isoformat()

	def reset_daily_period_if_needed(self):
		today = self.current_utc_date()
		if self.daily_reset_date == today:
			return

		for players in self.players.values():
			for player in players.values():
				player["daily_xp"] = 0
		self.daily_reset_date = today
		self.save()

	def get_server_players(self, guild_id):
		return self.players.setdefault(str(guild_id), {})

	def get_player(self, guild_id, user_id):
		players = self.get_server_players(guild_id)
		user_key = str(user_id)
		if user_key not in players:
			players[user_key] = self.empty_player(user_id)
		return players[user_key]

	def add_player_xp(self, guild_id, user_id, amount):
		player = self.get_player(guild_id, user_id)
		player["xp"] += amount
		player["daily_xp"] += amount
		return player

	def get_leaderboard(self, guild_id, leaderboard_type):
		players = self.get_server_players(guild_id)
		xp_key = "daily_xp" if leaderboard_type == "daily" else "xp"
		return sorted(
			players.items(),
			key=lambda item: item[1].get(xp_key, 0),
			reverse=True,
		)[:10]

	def get_server_settings(self, guild_id):
		return self.servers.get(
			str(guild_id),
			{"category": "general", "difficulty": "any"},
		)

	def set_server_settings(self, guild_id, settings):
		self.servers[str(guild_id)] = settings
