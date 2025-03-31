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
    print(f'✅ Logged in as {bot.user}')
    for guild in bot.guilds:
        await get_log_channel(guild)

@bot.event
async def on_guild_channel_create(channel):
    if channel.guild.owner_id not in whitelisted:
        await channel.delete()
        member = channel.guild.get_member(channel.guild.owner_id)
        if member:
            await member.ban(reason="Unauthorized channel creation")
    log_channel = await get_log_channel(channel.guild)
    embed = create_log_embed("📂 Channel Created", discord.Color.red(), {"Channel": channel.mention})
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    log_channel = await get_log_channel(channel.guild)
    embed = create_log_embed("🚮 Channel Deleted", discord.Color.red(), {"Channel": channel.name})
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_create(role):
    await role.delete()
    log_channel = await get_log_channel(role.guild)
    embed = create_log_embed("⚠️ Role Created & Removed", discord.Color.red(), {"Role": role.name})
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    log_channel = await get_log_channel(role.guild)
    embed = create_log_embed("🚨 Role Deleted", discord.Color.red(), {"Role": role.name})
    await log_channel.send(embed=embed)

@bot.event
async def on_member_update(before, after):
    added_roles = [role for role in after.roles if role not in before.roles]
    if added_roles:
        for role in added_roles:
            await after.remove_roles(role)
        log_channel = await get_log_channel(after.guild)
        embed = create_log_embed("⚠️ Unauthorized Role Assignment", discord.Color.red(), {"User": after.mention, "Removed Role": ', '.join([role.name for role in added_roles])})
        await log_channel.send(embed=embed)
        await after.ban(reason="Unauthorized role assignment")

@bot.event
async def on_member_join(member):
    if member.bot:
        adder = None
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add):
            if entry.target == member:
                adder = entry.user
                break
        if adder:
            await adder.ban(reason="Unauthorized bot addition")
        await member.kick(reason="Bots are not allowed")
    
bot.run(TOKEN)
