import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}

def create_log_embed(title, color, fields):
    embed = discord.Embed(title=title, color=color)
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
    return embed

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for guild in bot.guilds:
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel("security-logs")
            print(f"Created log channel in {guild.name}")

@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        creator = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = create_log_embed("🆕 Channel Created", discord.Color.green(), {
                "Channel": f"{channel.name} ({channel.mention})",
                "Created By": f"{creator.mention} ({creator.id})"
            })
            await log_channel.send(embed=embed)
        if creator.id not in whitelisted:
            await channel.delete()
            await channel.guild.ban(creator, reason="Unauthorized channel creation")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = create_log_embed("❌ Channel Deleted", discord.Color.red(), {
                "Channel": f"{channel.name}",
                "Deleted By": f"{deleter.mention} ({deleter.id})"
            })
            await log_channel.send(embed=embed)
        if deleter.id not in whitelisted:
            await channel.guild.ban(deleter, reason="Unauthorized channel deletion")

@bot.event
async def on_message_delete(message):
    log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
    async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
        if entry.target.id == message.author.id:
            deleter = entry.user
            break
    else:
        deleter = "Unknown"

    if log_channel:
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.orange())
        embed.add_field(name="Deleted Message", value=message.content or "Embed/Attachment", inline=False)
        embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter.id})" if deleter != "Unknown" else "Could not determine", inline=False)
        embed.add_field(name="Message Author", value=f"{message.author.mention} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
        
        await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    log_channel = discord.utils.get(before.guild.text_channels, name="security-logs")
    if log_channel:
        embed = create_log_embed("✏️ Message Edited", discord.Color.blue(), {
            "Before": before.content,
            "After": after.content,
            "Edited By": f"{before.author.mention} ({before.author.id})",
            "Channel": before.channel.mention
        })
        await log_channel.send(embed=embed)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            giver = entry.user
            if giver.id not in whitelisted:
                for role in after.roles:
                    if role not in before.roles:
                        await after.remove_roles(role)
                        print(f"Removed role {role} from {after}")
                await after.guild.ban(giver, reason="Unauthorized role grant")
                log_channel = discord.utils.get(after.guild.text_channels, name="security-logs")
                if log_channel:
                    await log_channel.send(f"{giver} tried to give a role, action reverted and user banned!")

@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = discord.utils.get(member.guild.text_channels, name="security-logs")
    if before.channel != after.channel:
        if after.channel and log_channel:
            await log_channel.send(f"{member} joined voice channel {after.channel}")
        elif before.channel and log_channel:
            await log_channel.send(f"{member} left voice channel {before.channel}")
    if before.mute != after.mute:
        action = "server muted" if after.mute else "server unmuted"
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
            await log_channel.send(f"{member} was {action} by {entry.user}.")
    if before.deaf != after.deaf:
        action = "server deafened" if after.deaf else "server undeafened"
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
            await log_channel.send(f"{member} was {action} by {entry.user}.")

@bot.command()
async def whitelist(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.add(member.id)
        await ctx.send(f"{member} has been added to the whitelist!")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.discard(member.id)
        await ctx.send(f"{member} has been removed from the whitelist!")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command()
async def check_whitelist(ctx):
    await ctx.send(f"Whitelisted Users: {', '.join(str(user) for user in whitelisted)}")

@bot.command()
async def join_vc(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined voice channel {channel}")
    else:
        await ctx.send("You need to be in a voice channel for me to join!")

async def ban_user(guild, user, reason="Violation of server rules"):
    try:
        dm_message = discord.Embed(title="🚨 You have been banned!", color=discord.Color.red())
        dm_message.add_field(name="Server", value=guild.name, inline=False)
        dm_message.add_field(name="Reason", value=reason, inline=False)
        
        try:
            await user.send(embed=dm_message)
        except discord.Forbidden:
            print(f"⚠️ Could not send DM to {user}.")

        await guild.ban(user, reason=reason)
    except discord.Forbidden:
        print(f"❌ Missing permissions to ban {user}!")

bot.run(TOKEN)
