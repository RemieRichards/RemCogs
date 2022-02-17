# Standard Library
import typing
import calendar
from math import ceil
from math import floor

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
                await ctx.send(ctx.author.mention+" loans "+str(amount)+" "+str(await bank.get_currency_name(ctx.guild))+loan_txt+" to "+user.mention)
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
    
        loan = await self.get_loan(ctx, user, ctx.author)
        if loan is None:
            await ctx.send("You don't owe "+user.display_name+" any "+str(await bank.get_currency_name(ctx.guild)))
    
        repaying = loan.get_outstanding()
        if repayment is not None:
            repaying = min(loan.get_outstanding(),repayment)
        
        if await bank.can_spend(ctx.author, repaying):
            await ctx.send(ctx.author.mention+" repays "+str(repaying)+" "+str(await bank.get_currency_name(ctx.guild))+" to "+user.mention)
            try:       
                await loan.repay(repaying) 
                await bank.withdraw_credits(ctx.author, repaying)
                await bank.deposit_credits(user, repaying)
            except BalanceTooHigh as e:
                await bank.set_balance(user, e.max_balance)
        else:
            await ctx.send(ctx.author.mention+" you can't afford that much!")

    @commands.guild_only()
    @_loan.command()
    async def forgive(self, ctx: commands.Context, user: discord.Member):
        """Forgive the debt you're owed..."""
        
        loan = await self.get_loan(ctx, ctx.author, user)
        if loan is not None:
            await ctx.send(ctx.author.mention+" forgives a debt of "+str(loan.get_outstanding())+" "+str(await bank.get_currency_name(ctx.guild))+" from "+user.mention+"!")
            await loan.clear_loan()         
        else:
            await ctx.send(user.display_name+" doesn't owe you any "+str(await bank.get_currency_name(ctx.guild))+"!")
        

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
        loans.sort(key=lambda x: x.get_loanee().display_name)
        
        if len(loans)==0:
            whom = "You have"
            if loans_for is not ctx.author:
                whom = loans_for.display_name+" has"        
            await ctx.send(whom+" no loans!")
            return

        pound_len = max(4, len(str(len(loans)))+2)
               
        loanee_names = []
        amounts = []
        final_amounts = []
        has_interest = False
        for i, loan in enumerate(loans):
            loanee = loan.get_loanee()
            loanee_names.append(loanee.display_name)
            amounts.append(loan.get_pre_interest_amount())
            final_amounts.append(loan.get_outstanding())
            if not has_interest and loan.interest is not None:
                has_interest = True
            
        loanee_len = max(8, len(loanee_names[len(loanee_names)-1])+2)
        
        amount_len0 = len(str(amounts[len(amounts)-1]))
        amount_len = max(8, amount_len0)
        if has_interest:
            amount_len = max(9, amount_len0+2) #9 not 8 as the title changes to "Initial"
        
        interest_len0 = len(str(final_amounts[len(final_amounts)-1]))
        interest_len = max(10, interest_len0+2)

        header = "{pound:{pound_len}}{loanee:{loanee_len}}{amount:{amount_len}}"
        if has_interest:
            header += "{interest:{interest_len}}Outstanding"
        header += "\n"
        header = header.format(
            pound="#",
            loanee="Loanee",
            amount="Initial" if has_interest else "Amount",
            interest="Interest",
            pound_len=pound_len,
            loanee_len=loanee_len,
            amount_len=amount_len,
            interest_len=interest_len
        )
        
        temp_msg = header       
        embed_requested = await ctx.embed_requested()
        base_embed = discord.Embed()       
        base_embed.set_author(name=loans_for.display_name+"'s Loans", icon_url=loans_for.avatar_url)
        loan_pages = []
        pos = 1

        for i, loan in enumerate(loans):
            loanee = loan.get_loanee()
            amount = loan.get_pre_interest_amount()
            
            interest0 = loan.interest
            if interest0 is None:
                interest0 = 0
            interest = str(interest0)+"%"

            temp_msg += (
                f"{f'{humanize_number(pos)}.': <{pound_len-1}} "
                f"{f'{loanee.display_name}': <{loanee_len-1}} "
                f"{f'{amount}': <{amount_len-1}} "
            )
            
            if has_interest:
                temp_msg += f"{f'{interest}': <{interest_len}}" #no -1, as % symbol
                temp_msg += f"{loan.get_outstanding()}\n"
                
            
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loans)/10))
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
                    text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loans)/10))
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
    @_loan.command()
    async def debtboard(self, ctx: commands.Context):
        """Who owes who what?"""
    
        loans = await self.list_all_loans(ctx)
        loans.sort(key=lambda x: x.get_outstanding(), reverse=True)
        
        if len(loans)==0:      
            await ctx.send("Nobody has any loans!")
            return

        pound_len = max(4, len(str(len(loans)))+2)
        
        loaner_names = []
        loanee_names = []
        amounts = []
        for i, loan in enumerate(loans):
            loaner = loan.get_loaner()
            loanee = loan.get_loanee()
            loaner_names.append(loaner.display_name)
            loanee_names.append(loanee.display_name)
            amounts.append(loan.get_outstanding())
            
        loaner_len = max(8, len(loaner_names[len(loaner_names)-1])+2)
        loanee_len = max(8, len(loanee_names[len(loanee_names)-1])+2)
        
        amount_len = max(11, len(str(amounts[len(amounts)-1])))

        header = "{pound:{pound_len}}{loaner:{loaner_len}}{loanee:{loanee_len}}{amount:{amount_len}}\n".format(
            pound="#",
            loaner="Loaner",
            loanee="Loanee",
            amount="Outstanding",
            pound_len=pound_len,
            loaner_len=loaner_len,
            loanee_len=loanee_len,
            amount_len=amount_len
        )
        
        temp_msg = header       
        embed_requested = await ctx.embed_requested()
        base_embed = discord.Embed()
        base_embed.set_author(name=ctx.guild.name+" - Loans", icon_url=ctx.guild.icon_url)
        loan_pages = []
        pos = 1

        for i, loan in enumerate(loans):
            loaner = loan.get_loaner()
            loanee = loan.get_loanee()
            amount = loan.get_outstanding()

            temp_msg += (
                f"{f'{humanize_number(pos)}.': <{pound_len-1}} "
                f"{f'{loaner.display_name}': <{loaner_len-1}} "
                f"{f'{loanee.display_name}': <{loanee_len-1}} "               
                f"{f'{amount}': <{amount_len-1}}\n"
            )
            
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loans)/10))
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
                    text="Page "+str(len(loan_pages)+1)+"/"+str(ceil(len(loans)/10))
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
               
        curr_time = calendar.timegm(ctx.message.created_at.utctimetuple())
        
        current_loan = loans.get(loaner_key).get(loanee_key)
        if current_loan is None:
            loans[loaner_key][loanee_key] = {"original_amount": amount, "outstanding": amount, "interest": interest, "created_at": curr_time, "loaner": loaner_key, "loanee": loanee_key}
        else:
            curr_name = str(await bank.get_currency_name(ctx.guild))   
            curr_amount = loans[loaner_key][loanee_key]["outstanding"] 
            loans[loaner_key][loanee_key]["outstanding"] += amount
            loans[loaner_key][loanee_key]["created_at"] = curr_time
            
            loan_update_msg = loanee.mention+" already owes "+loaner.mention+" "+str(curr_amount)+" "+curr_name+", that loan has been extended ("+str(loans[loaner_key][loanee_key]["outstanding"])+" "+curr_name+")"
            
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

    # Loans where we are the loaner
    async def list_loans(self, ctx: commands.Context, loaner: discord.Member):
        ret = []
        for i, loan in enumerate(await self.list_all_loans(ctx)):
            if loan.loaner_key==str(loaner.id):
                ret.append(loan)
        return ret
    
    # Loans where we are the loanee
    async def list_debts(self, ctx: commands.Context, loanee: discord.Member):
        ret = []      
        for i, loan in enumerate(await self.list_all_loans(ctx)):
            if loan.loanee_key==str(loanee.id):
                ret.append(loan)
        return ret
    
    # Get Loaner's loan to Loanee
    async def get_loan(self, ctx: commands.Context, loaner: discord.Member, loanee: discord.Member):
        loans = await self.config.guild(ctx.guild).loans()      
        loaner_key = str(loaner.id)
        loanee_key = str(loanee.id)
        if loans.get(loaner_key):
            loan_dict = loans[loaner_key]
            if loan_dict.get(loanee_key):
                return Loan(ctx, self.config, loan_dict[loanee_key])
        return None
        
    # All loans as a list
    async def list_all_loans(self, ctx: commands.Context):
        loans = await self.config.guild(ctx.guild).loans()
        ret = []
        for i, loaner in enumerate(loans.keys()):
            loan_dict = loans[loaner]     
            for i, loanee in enumerate(loan_dict.keys()):
                ret.append(Loan(ctx, self.config, loan_dict[loanee]))
        return ret




class Loan():
    def __init__(self, ctx, config, loan0):
        self.ctx = ctx
        self.config = config
        self.loan0 = loan0
        
        self.loaner_key      = loan0["loaner"]
        self.loanee_key      = loan0["loanee"]
        self.outstanding     = loan0["outstanding"]
        self.original_amount = self.outstanding
        
        if loan0.get("original_amount"):
            self.original_amount = loan0["original_amount"] #OLD DATA HACK
             
        self.timestamp = None
        if loan0.get("created_at"):
            self.timestamp = loan0["created_at"]
        else:
            self.timestamp = calendar.timegm(self.ctx.message.created_at.utctimetuple())  #OLD DATA HACK
        
        self.interest = None
        if loan0.get("interest"):
            self.interest = loan0["interest"]     


    def get_loaner(self):
       return self.ctx.guild.get_member(int(self.loaner_key))
        
    def get_loanee(self):
        return self.ctx.guild.get_member(int(self.loanee_key))

    def get_pre_interest_amount(self):
        return self.outstanding

    def get_outstanding(self):
        if self.interest is None:
            return self.outstanding
        cur_time = calendar.timegm(self.ctx.message.created_at.utctimetuple()) 
        days = floor((cur_time - self.timestamp) / 86400) + 1;
        return self.outstanding + ceil((self.outstanding * (self.interest/100)) * days)

    async def repay(self, amount):
        curr_outstanding = self.get_outstanding()   
        curr_outstanding -= amount
        if curr_outstanding <= 0:
            await self.clear_loan()
        else:
            self.loan0["outstanding"] = curr_outstanding
            loans = await self.config.guild(self.ctx.guild).loans()   
            loans[self.loaner_key][self.loanee_key] = self.loan0
            await self.config.guild(self.ctx.guild).loans.set(loans)  
    
    async def clear_loan(self):
        loans = await self.config.guild(self.ctx.guild).loans() 
        loans[self.loaner_key].pop(self.loanee_key, None)
        await self.config.guild(self.ctx.guild).loans.set(loans)
        