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

# Channel Creation/Deletion Ban
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id not in whitelisted:
            await channel.delete()
            await entry.user.ban(reason="Unauthorized channel creation")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚫 Channel Created & User Banned", discord.Color.red(), {"User": entry.user.mention})
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized channel deletion")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚫 Channel Deleted & User Banned", discord.Color.red(), {"User": entry.user.mention})
            await log_channel.send(embed=embed)

# Role Creation/Deletion Ban
@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id not in whitelisted:
            await role.delete()
            await entry.user.ban(reason="Unauthorized role creation")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚫 Role Created & User Banned", discord.Color.red(), {"User": entry.user.mention})
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized role deletion")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚫 Role Deleted & User Banned", discord.Color.red(), {"User": entry.user.mention})
            await log_channel.send(embed=embed)

# Role Assignment Ban
@bot.event
async def on_member_update(before, after):
    added_roles = [role for role in after.roles if role not in before.roles]
    if added_roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            if entry.user.id not in whitelisted and entry.user != after:
                await entry.user.ban(reason="Unauthorized role assignment")
                for role in added_roles:
                    await after.remove_roles(role)
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🚫 Unauthorized Role Given & User Banned", discord.Color.red(), {
                    "User": entry.user.mention,
                    "Removed Role": ', '.join([role.name for role in added_roles])
                })
                await log_channel.send(embed=embed)

# Bot Addition Ban
@bot.event
async def on_member_join(member):
    if member.bot:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id not in whitelisted:
                await entry.user.ban(reason="Unauthorized bot addition")
                await member.kick(reason="Bots are not allowed")
                log_channel = await get_log_channel(member.guild)
                embed = create_log_embed("🚫 Unauthorized Bot Added & User Banned", discord.Color.red(), {"User": entry.user.mention})
                await log_channel.send(embed=embed)

# Whitelist Commands
@bot.command()
async def whitelist(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.add(member.id)
        await ctx.send(f"✅ {member} has been added to the whitelist!")
    else:
        await ctx.send("🚫 You are not authorized to use this command.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.discard(member.id)
        await ctx.send(f"❌ {member} has been removed from the whitelist!")
    else:
        await ctx.send("🚫 You are not authorized to use this command.")

bot.run(TOKEN)
