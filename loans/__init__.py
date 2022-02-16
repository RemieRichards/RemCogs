from .loans import Loanshark


def setup(bot):
    bot.add_cog(Loanshark(bot))