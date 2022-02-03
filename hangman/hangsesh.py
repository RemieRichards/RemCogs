# Standard Library
import asyncio
import random
import csv

# Red
from redbot.core import bank
from redbot.core.i18n import Translator
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.data_manager import bundled_data_path

# Discord
import discord

##TODO:
## - ability to guess the word by typing "guess YOURWORD" (not just word as you may want to talk while playing)

class HangmanSession:
    async def play(self, ctx):
        self.datapath = bundled_data_path(self)
        self.mistakes = 0
        self.last_guess_good = None
        self.guessed_letters = {}
        await self.pick_word(ctx)
        await self.hangman_loop(ctx)
    
    async def pick_word(self, ctx):
        try:
            with open(self.datapath / "words.txt") as f:
                wordlist = f.read().splitlines()
        except FileNotFoundError:
            await ctx.send("No wordlist??")
            return None
        
        self.word = random.choice(wordlist)        
        print(self.word)
        self.word_guessing = ""
        for i,c in enumerate(self.word):
            if c == "-":
                self.word_guessing += "-"
            elif c == " ":
                self.word_guessing += " "
            else:
                self.word_guessing += "_"

    async def hangman_loop(self, ctx, message=None):
        embed = self.word_embed(ctx)
        if message is not None:
            await message.edit(content=ctx.author.mention, embed=embed)
        else: 
            message = await ctx.send(ctx.author.mention, embed=embed)
        guess = await self.get_guess(ctx)
        if guess == None:
            await ctx.send(ctx.author.mention+" time's up! the word was **"+self.word+"**")
            return
        else:
            await self.guess(ctx, guess)
            if self.check_loss():
                await message.edit(embed=self.word_embed(ctx, False))
                return
            if self.check_win():
                winnings = random.randint(1,5)
                await message.edit(embed=self.word_embed(ctx, True, winnings))
                try:
                    await bank.deposit_credits(ctx.author, winnings)           
                except BalanceTooHigh as e:
                    await bank.set_balance(ctx.author, e.max_balance)
                return
            else:
                await self.hangman_loop(ctx, message)
    
    def word_embed(self, ctx, won=False, winnings=0):
        word_output = ""
        
        for i, c in enumerate(self.word_guessing):
            if i != 0:
                word_output += " "
                
            word_output += c
            
        desc = "```\n"       
        
        desc += "  + - - - + \n"
        desc += "  |       | \n"
        
        #victim, code is bad cos lazy    
        if self.mistakes >= 1:
            desc += "  O       | \n"
        else:
            desc += "          | \n"
        
        if self.mistakes >= 2:
            if self.mistakes >= 3:
                if self.mistakes >= 4:
                    desc += " /|\      | \n"
                else:
                    desc += " /|       | \n"                
            else:
                desc += "  |       | \n"
        else:
            desc += "          | \n"       
        if self.mistakes >= 5:
            if self.mistakes >= 6:
                desc += " / \\      | \n"
            else:
                desc += " /        | \n"
        else:
            desc += "          | \n"

        desc += "          | \n"        
        desc += " ===========\n\n"

        desc += word_output
        desc += "```\n"
        
        if len(self.guessed_letters)>0:
            desc += "Guessed: "
            first = True
            for i, letter in enumerate(self.guessed_letters.keys()):
                if not first:
                    desc += ", "
                desc += str(letter)
                first = False
            desc += "\n"          
            
        if self.mistakes > 0:
            desc += str(self.mistakes)+"/6 mistakes\n"

        colour = 0x20B2AA
        if self.last_guess_good == True:
            colour = 0xFEF000
        if self.last_guess_good == False:
            colour = 0xFF0000      
        if won == True:
            colour = 0x00FF00
            desc += "You won!"
            desc += "\nYou receive "+str(winnings)+(" credits!" if winnings>1 else " credit!")
            
        if self.mistakes == 6:
            colour = 0x000000
            desc = "```"
            desc += "  /-------\\-\\\n"
            desc += " /---------\\-\\\n"
            desc += " |    |    | |\n"
            desc += " |   ---   | |\n"
            desc += " |    |    | |\n"
            desc += " |    |    | |\n"
            desc += " |         | |\n"
            desc += " |   RIP   | |\n"
            desc += "/           \ \\\n"
            desc += "---------------\n"
            desc += "```\n"
            desc += "You lose!\n"
            desc += "The word was **"+self.word+"**"
        

        embed = discord.Embed(description=desc, colour=colour)
        return embed
        
    
    async def get_guess(self, ctx):
        try:        
            def check_msg(m):
                return len(m.content.lower())==1
            
            msg = await ctx.bot.wait_for("message", check=check_msg, timeout=60)
            guess = msg.content.lower()
            await msg.delete()
            return guess
        except asyncio.TimeoutError:
            return None
        return None
    
    async def guess(self, ctx, g):
        if g in self.guessed_letters:
            return
    
        self.guessed_letters[g] = True
        success = False
        for i, c in enumerate(self.word):
            if c == g:
                success = True
                self.word_guessing = self.word_guessing[:i] + g + self.word_guessing[i+1:]
                
        if not success:
            self.mistakes += 1
            
        self.last_guess_good = success
                
    def check_win(self):
        return self.word_guessing == self.word
        
    def check_loss(self):
        return self.mistakes >= 6