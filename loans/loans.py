# Standard Library
import typing
from math import ceil

# Red
from redbot.core import bank
from redbot.core import commands
from redbot.core import Config
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.chat_formatting import box, humanize_number
from redbot.core.utils.menus import close_menu, menu, DEFAULT_CONTROLS
from redbot.core.errors import BalanceTooHigh

# Discord
import discord


class Loanshark(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=14)
        default_loan_data = {
            "loans": {},
        }
        self.config.register_guild(**default_loan_data)

    @commands.guild_only()
    @commands.group(name="loan")
    async def _loan(self, ctx: commands.Context):
        """Base command to manage loans."""
        pass

    @commands.guild_only()
    @_loan.command()
    async def give(self, ctx: commands.Context, user: discord.Member, amount: int, interest: typing.Optional[int]):
        """Lend a friend some currency, they *will* pay you back eventually.
        
        Examples:
            - `[p]loan give user amount` - Loans 'amount' to 'user'.
            - `[p]loan give user amount interest` - Loans 'amount' to 'user', with an interest rate of 'interest'
        """
        
        
        loans = await self.config.guild(ctx.guild).loans()
        
        if await bank.can_spend(ctx.author, amount):
            if ctx.author is user:
                await ctx.send("TODO: don't let people self-loan, but need for testing rn")
            
            loan_txt = ""
            if interest is not None:
                loan_txt = " (@ "+str(interest)+"% interest)"
        
            loan_offer = await ctx.send(ctx.author.mention+" offers to loan "+str(amount)+" "+str(await bank.get_currency_name(ctx.guild))+loan_txt+" to "+user.mention+", do they accept?")
            start_adding_reactions(loan_offer, ReactionPredicate.YES_OR_NO_EMOJIS)
            pred = ReactionPredicate.yes_or_no(loan_offer, user)
            await ctx.bot.wait_for("reaction_add", check=pred)
            if pred.result is True:
                await loan_offer.delete()
                await ctx.send(ctx.author.mention+" loans "+str(amount)+" "+str(await bank.get_currency_name(ctx.guild))+" to "+user.mention)
                try:
                    await self.record_loan(ctx, ctx.author, user, amount, interest)
                    await bank.withdraw_credits(ctx.author, amount)
                    await bank.deposit_credits(user, amount)
                except BalanceTooHigh as e:
                    await bank.set_balance(user, e.max_balance)
            else:
                await loan_offer.delete()
        else:
            await ctx.send(ctx.author.mention+" you can't afford that much!")
            
#    @commands.guild_only()        
#    @_loan.command()
#    async def collect(self, ctx: commands.Context, user: typing.Optional[discord.Member]):
#        
#        return
    
    @commands.guild_only()
    @_loan.command()
    async def repay(self, ctx: commands.Context, user: discord.Member, repayment: typing.Optional[int]):
        """Repay your debts.
        
        Examples:
            - `[p]loan repay user` - Attempts to repay the full amount of the debt.
            - `[p]loan repay user repayment` - Attempts to repay the specified amount.
        """
    
        loan = await self.get_debt(ctx, ctx.author, user)
        if loan is None:
            await ctx.send("You don't owe "+user.display_name+" any "+str(await bank.get_currency_name(ctx.guild)))
    
        repaying = loan["outstanding"]
        if repayment is not None:
            repaying = min(loan["outstanding"],repayment)
        
        if await bank.can_spend(ctx.author, repaying):
            await ctx.send(ctx.author.mention+" repays "+str(repaying)+" "+str(await bank.get_currency_name(ctx.guild))+" to "+user.mention)
            try:       
                if repaying >= loan["outstanding"]:
                    await self.clear_loan(ctx, user, ctx.author)
                else:
                    await self.partial_repay_loan(ctx, user, ctx.author, repaying)  
                await bank.withdraw_credits(ctx.author, repaying)
                await bank.deposit_credits(user, repaying)
            except BalanceTooHigh as e:
                await bank.set_balance(user, e.max_balance)
        else:
            await ctx.send(ctx.author.mention+" you can't afford that much!")
            
    
    @commands.guild_only()        
    @_loan.command()
    async def list(self, ctx: commands.Context, user: typing.Optional[discord.Member]):
        """View your capitalist empire
        
        Examples:
            - `[p]loan list` - Lists all loans where you are the Loaner
            - `[p]loan list user` - Lists all loans where 'user' is the Loaner
        """
    
        loans_for = ctx.author
        if user is not None:
            loans_for = user        
            
        loans = await self.list_loans(ctx, loans_for)        

        loan_keys = list(loans.keys())
        loan_keys.sort(key=len)
        
        if len(loan_keys)==0:
            whom = "You have"
            if user is not ctx.author:
                whom = user.display_name+" has"        
            await ctx.send(whom+" no loans!")
            return

        pound_len = len(str(len(loan_keys)))
               
        loanee_names = []
        amounts = []
        has_interest = False
        for i, loanee0 in enumerate(loan_keys):
            loanee = ctx.guild.get_member(int(loanee0))
            loanee_names.append(loanee.display_name)
            loan = loans[loanee0]
            amounts.append(loan["outstanding"])
            if not has_interest and loan["interest"] is not None:
                has_interest = True
            
        loanee_names.sort(key=len)
        loanee_len = len(loanee_names[len(loanee_names)-1])
        
        amounts.sort()
        amount_len = len(str(amounts[len(amounts)-1]))
        
        header = "{pound:{pound_len}}{loanee:{loanee_len}}{amount:{amount_len}}"
        if has_interest:
            header += "{interest:{interest_len}}"
        header += "\n"
        header = header.format(
            pound="#",
            loanee="Loanee",
            amount="Amount",
            interest="Interest",
            pound_len=pound_len+3,
            loanee_len=loanee_len+3,
            amount_len=amount_len+3 if has_interest else amount_len,
            interest_len=3
        )
        
        temp_msg = header       
        embed_requested = await ctx.embed_requested()
        base_embed = discord.Embed(title=loans_for.display_name+"'s Loans")
        loan_pages = []
        pos = 1

        for i, loanee0 in enumerate(loan_keys):
            loan = loans[loanee0]
            loanee = ctx.guild.get_member(int(loanee0))
            amount = loan["outstanding"]
            
            interest0 = loan["interest"]
            if interest0 is None:
                interest0 = 0
            interest = str(interest0)+"%"
            
            amount_len_line = amount_len+2
            if not has_interest:
                interest = ""
                amount_len_line = amount_len
            temp_msg += (
                f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                f"{f'{loanee.display_name}': <{loanee_len+2}} "               
                f"{f'{amount}': <{amount_len_line}} "
                f"{interest}\n"
            )
            
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loan_keys)/10))
                    )
                    loan_pages.append(embed)
                else:
                    loan_pages.append(box(temp_msg, lang="md"))
                temp_msg = header
            pos += 1
        
        if temp_msg != header:
            if embed_requested:
                embed = base_embed.copy()
                embed.description = box(temp_msg, lang="md")
                embed.set_footer(
                    text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loan_keys)/10))
                )
                loan_pages.append(embed)
            else:
                loan_pages.append(box(temp_msg, lang="md"))
                
        await menu(
            ctx,
            loan_pages,
            DEFAULT_CONTROLS if len(loan_pages) > 1 else {"\N{CROSS MARK}": close_menu},
        )

    @commands.guild_only()
    @commands.is_owner()
    @_loan.command()
    async def clear_all_debts(self, ctx):
        """No loan sharks were harmed in the making of this cog."""
    
        await self.config.clear_all()   
        await ctx.send("Done!")
    
    
    
    
    async def record_loan(self, ctx: commands.Context, loaner: discord.Member, loanee: discord.Member, amount: int, interest: typing.Optional[int]):  
        loaner_key = str(loaner.id)
        loanee_key = str(loanee.id)
        loans = await self.config.guild(ctx.guild).loans()
        if loans.get(loaner_key) is None:
            loans[loaner_key] = {}
        if loans.get(loaner_key).get(loanee_key) is None:
            loans[loaner_key][loanee_key] = None
            
        current_loan = loans.get(loaner_key).get(loanee_key)
        if current_loan is None:
            loans[loaner_key][loanee_key] = {"outstanding": amount, "interest": interest}
        else:
            curr_name = str(await bank.get_currency_name(ctx.guild))
            loans[loaner_key][loanee_key]["outstanding"] += amount
            
            loan_update_msg = loanee.mention+" already owes "+loaner.mention+" "+str(current_loan["outstanding"])+" "+curr_name+", that loan has been extended ("+str(loans[loaner_key][loanee_key]["outstanding"])+" "+curr_name+")"
            
            if interest is not None:
                if (interest is not None and current_loan["interest"] is None) or (interest is not current_loan["interest"]):
                    loan_update_msg += "\nThe interest rate has been updated to "+str(interest)+"%"
                    current_loan["interest"] = interest
            else:
                if current_loan["interest"] is not None:
                    loan_update_msg += "\nThe interest rate has been removed"
                    current_loan["interest"] = None
                    
            await ctx.send(loan_update_msg)
                
        await self.config.guild(ctx.guild).loans.set(loans)
    
    
    async def clear_loan(self, ctx: commands.Context, loaner: discord.Member, loanee: discord.Member):
        loans = await self.config.guild(ctx.guild).loans()
        loan = await self.get_debt(ctx, loanee, loaner)
        if loan is None:
            return
            
        loaner_key = str(loaner.id)
        loanee_key = str(loanee.id)
        loans[loaner_key].pop(loanee_key, None)

        await self.config.guild(ctx.guild).loans.set(loans)
    
    async def partial_repay_loan(self, ctx: commands.Context, loaner: discord.Member, loanee: discord.Member, repaying: int):
        loans = await self.config.guild(ctx.guild).loans()
        loan = await self.get_debt(ctx, loanee, loaner)
        if loan is None:
            return         
        loan["outstanding"] = loan["outstanding"]-repaying
        loaner_key = str(loaner.id)
        loanee_key = str(loanee.id)
        loans[loaner_key][loanee_key] = loan
        if loan["outstanding"] <= 0:
            await self.clear_loan(ctx, loaner, loanee)
        else:
            await self.config.guild(ctx.guild).loans.set(loans)   
    
    # Loans where we are the loaner
    async def list_loans(self, ctx: commands.Context, loaner: discord.Member):
        loans = await self.config.guild(ctx.guild).loans()
        loaner_key = str(loaner.id)
        if loans.get(loaner_key):
            return loans[loaner_key]
        else:
            return {}
    
    # Loans where we are the loanee
    async def list_debts(self, ctx: commands.Context, loanee: discord.Member):
        loans = await self.config.guild(ctx.guild).loans()
        ret = []
        for i, loaner in enumerate(loans.keys()):
            loan_dict = loans[loaner]     
            if loans.get(loanee.id):
                loan = loan_dict[loanee.id]
                ret.append({"outstanding": loan["outstanding"], "interest": loan["interest"], "loaner": loaner}) 
        return ret
    
    # Get Loanee's debt with Loaner
    async def get_debt(self, ctx: commands.Context, loanee: discord.Member, loaner: discord.Member):
        loans = await self.config.guild(ctx.guild).loans()      
        loaner_key = str(loaner.id)
        loanee_key = str(loanee.id)
        if loans.get(loaner_key):
            loan_dict = loans[loaner_key]
            if loan_dict.get(loanee_key):  
                return loan_dict[loanee_key]
        return None
        
        