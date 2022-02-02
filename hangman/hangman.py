from redbot.core import commands
from .hangsesh import HangmanSession

class Hangman(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hangman(self, ctx):
        await HangmanSession().play(ctx)