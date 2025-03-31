import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
from datetime import datetime

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}

# Regex pattern for detecting links
LINK_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

def create_log_embed(title, color, fields):
    embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    return embed

async def get_log_channel(guild):
    log_channel = discord.utils.get(guild.text_channels, name="security-logs")
    if log_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False),
            guild.me: discord.PermissionOverwrite(send_messages=True)
        }
        log_channel = await guild.create_text_channel(
            "security-logs",
            overwrites=overwrites,
            reason="Automatic log channel creation"
        )
    return log_channel

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for guild in bot.guilds:
        await get_log_channel(guild)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check for links
    if LINK_PATTERN.search(message.content):
        if message.author.id not in whitelisted:
            await message.delete()
            await message.author.send("Links are not allowed in this server.")
            
            log_channel = await get_log_channel(message.guild)
            embed = create_log_embed("🚨 Link Deleted", discord.Color.red(), {
                "User": f"{message.author.mention} ({message.author.id})",
                "Deleted Link": message.content,
                "Channel": message.channel.mention
            })
            await log_channel.send(embed=embed)

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = await get_log_channel(member.guild)
    
    # User joined a voice channel
    if not before.channel and after.channel:
        embed = create_log_embed("🎤 Voice Channel Join", discord.Color.green(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": after.channel.mention,
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User left a voice channel
    elif before.channel and not after.channel:
        embed = create_log_embed("🚪 Voice Channel Leave", discord.Color.blue(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": before.channel.mention,
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User moved between voice channels
    elif before.channel and after.channel and before.channel != after.channel:
        embed = create_log_embed("🔄 Voice Channel Move", discord.Color.gold(), {
            "User": f"{member.mention} ({member.id})",
            "From": before.channel.mention,
            "To": after.channel.mention,
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User was server muted
    elif not before.mute and after.mute:
        embed = create_log_embed("🔇 User Server Muted", discord.Color.orange(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": before.channel.mention if before.channel else "N/A",
            "Action By": "Server",
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User was server unmuted
    elif before.mute and not after.mute:
        embed = create_log_embed("🔊 User Server Unmuted", discord.Color.green(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": before.channel.mention if before.channel else "N/A",
            "Action By": "Server",
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User was server deafened
    elif not before.deaf and after.deaf:
        embed = create_log_embed("🧏 User Server Deafened", discord.Color.orange(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": before.channel.mention if before.channel else "N/A",
            "Action By": "Server",
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User was server undeafened
    elif before.deaf and not after.deaf:
        embed = create_log_embed("🔊 User Server Undeafened", discord.Color.green(), {
            "User": f"{member.mention} ({member.id})",
            "Channel": before.channel.mention if before.channel else "N/A",
            "Action By": "Server",
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    # User was disconnected by force
    elif before.channel and after.channel is None and member.voice and member.voice.afk:
        embed = create_log_embed("👢 User Force Disconnected", discord.Color.red(), {
            "User": f"{member.mention} ({member.id})",
            "From": before.channel.mention,
            "Action By": "Server",
            "At": discord.utils.format_dt(discord.utils.utcnow(), 'T')
        })
    
    else:
        return
    
    await log_channel.send(embed=embed)

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

bot.run(TOKEN)
