import os

from discord import app_commands


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
TRIVIA_API_URL = "https://opentdb.com/api.php"
DEVELOPMENT_GUILD_ID = "1504712089535774820"
QUIZ_TIME_LIMIT = 20
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
