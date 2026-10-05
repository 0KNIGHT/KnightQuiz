import discord
from discord import app_commands

from config import (
	CATEGORY_CHOICES,
	CATEGORY_LABELS,
	DIFFICULTY_CHOICES,
	LEADERBOARD_CHOICES,
)


def register_commands(client, store, quiz_engine):
	@client.tree.command(name="quiz", description="Start a quiz")
	async def quiz(interaction: discord.Interaction):
		quiz_engine.cancel_timer()
		store.reset_daily_period_if_needed()
		guild_id = interaction.guild_id or 0
		user_id = interaction.user.id
		quiz_engine.active_quiz = None
		settings = store.get_server_settings(guild_id)
		question = await quiz_engine.get_question(guild_id, user_id, settings)
		store.save()
		quiz_engine.set_active_quiz(
			guild_id,
			user_id,
			interaction.channel,
			question,
		)
		options = question["options"]
		await interaction.response.send_message(
			f"🎯 Quiz time! {question['question']}\n"
			f"A) {options['A']}\n"
			f"B) {options['B']}\n"
			f"C) {options['C']}\n"
			f"D) {options['D']}"
		)
		quiz_engine.start_timer()

	@client.tree.command(
		name="quiz-settings",
		description="Configure this server's quiz settings",
	)
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
		settings = store.get_server_settings(interaction.guild.id).copy()
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
		store.set_server_settings(guild_id, settings)
		store.save()
		await interaction.response.send_message(
			f"Quiz settings updated: category = "
			f"{CATEGORY_LABELS[settings['category']]}, "
			f"difficulty = {settings['difficulty'].title()}."
		)

	@client.tree.command(name="help", description="Show KnightQuiz commands")
	async def help_command(interaction: discord.Interaction):
		embed = discord.Embed(
			title="KnightQuiz Help",
			description="Here are the available KnightQuiz commands:",
			color=discord.Color.blue(),
		)
		embed.add_field(name="/quiz", value="Start a quiz", inline=False)
		embed.add_field(
			name="/leaderboard",
			value="View the server leaderboard",
			inline=False,
		)
		embed.add_field(
			name="/quiz-settings",
			value="Configure server quiz settings",
			inline=False,
		)
		embed.add_field(
			name="/about",
			value="Learn about KnightQuiz",
			inline=False,
		)
		await interaction.response.send_message(embed=embed)

	@client.tree.command(name="about", description="Learn about KnightQuiz")
	async def about(interaction: discord.Interaction):
		embed = discord.Embed(
			title="🗡️ KnightQuiz",
			description=(
				"A Discord quiz bot built for fun, competition, and learning.\n\n"
				"**Features:**\n"
				"🎯 Random trivia questions\n"
				"⚡ XP & streaks\n"
				"🏆 Daily & lifetime leaderboards\n"
				"⚙️ Server-specific quiz settings\n\n"
				"Built by Knight0\n"
				"Version 1.0.0"
			),
			color=discord.Color.gold(),
		)
		await interaction.response.send_message(embed=embed)

	@client.tree.command(name="leaderboard", description="Show the top quiz players")
	@app_commands.describe(type="Which leaderboard to view")
	@app_commands.choices(type=LEADERBOARD_CHOICES)
	async def leaderboard(interaction: discord.Interaction, type: str):
		store.reset_daily_period_if_needed()
		if interaction.guild_id is None:
			await interaction.response.send_message(
				"The leaderboard can only be viewed inside a server."
			)
			return

		ranked_users = store.get_leaderboard(interaction.guild_id, type)
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
		store.reset_daily_period_if_needed()
		response = await quiz_engine.handle_answer(message)
		if response is not None:
			await message.channel.send(response)
