import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import re
from datetime import datetime
from collections import defaultdict
import asyncio
import json

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}
LINK_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

message_count = defaultdict(list)
BACKUP_FILE = "server_backup.json"

# 🔐 Backup Data
backup_data = {
    "roles": {},
    "channels": {},
    "permissions": {}
}

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
        log_channel = await guild.create_text_channel("security-logs", overwrites=overwrites)
    return log_channel

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    for guild in bot.guilds:
        await get_log_channel(guild)
        await backup_server_data(guild)
    auto_backup.start()

# 🔁 Automatic Backup Every 10 Minutes
@tasks.loop(minutes=10)
async def auto_backup():
    for guild in bot.guilds:
        await backup_server_data(guild)
    with open(BACKUP_FILE, 'w') as f:
        json.dump(backup_data, f, indent=2)

async def backup_server_data(guild):
    backup_data["roles"][str(guild.id)] = [(r.name, r.permissions.value) for r in guild.roles if not r.is_default()]
    backup_data["channels"][str(guild.id)] = [(c.name, str(c.type)) for c in guild.channels]

@bot.command()
async def restore(ctx):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("🚫 You are not authorized to use this command.")

    guild = ctx.guild
    await ctx.send("♻️ Restoring server structure...")

    for r_name, perms in backup_data["roles"].get(str(guild.id), []):
        await guild.create_role(name=r_name, permissions=discord.Permissions(perms))

    for c_name, c_type in backup_data["channels"].get(str(guild.id), []):
        if c_type == "text":
            await guild.create_text_channel(c_name)
        elif c_type == "voice":
            await guild.create_voice_channel(c_name)

    await ctx.send("✅ Server restoration completed!")

@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
        if entry.user.id not in whitelisted:
            member = guild.get_member(entry.user.id)
            if member:
                await member.edit(roles=[])
                await member.kick(reason="Unauthorized ban attempt")
                log_channel = await get_log_channel(guild)
                embed = create_log_embed("🚨 Unauthorized Ban Attempt - User Kicked", discord.Color.red(), {"User": entry.user.mention, "Banned User": user.mention})
                await log_channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    now = datetime.utcnow().timestamp()
    message_count[uid].append(now)
    message_count[uid] = [t for t in message_count[uid] if now - t < 5]

    if len(message_count[uid]) > 5:
        await mute_user(message.author)
        log_channel = await get_log_channel(message.guild)
        embed = create_log_embed("⚠️ User Muted for Spamming", discord.Color.orange(), {"User": message.author.mention, "Reason": "Excessive Messaging"})
        await log_channel.send(embed=embed)

    await bot.process_commands(message)

async def mute_user(member):
    guild = member.guild
    muted = discord.utils.get(guild.roles, name="Muted")
    if not muted:
        muted = await guild.create_role(name="Muted")
        for channel in guild.channels:
            await channel.set_permissions(muted, send_messages=False)
    await member.add_roles(muted)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id not in whitelisted:
            await channel.guild.ban(entry.user, reason="Unauthorized channel deletion")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🛑 Unauthorized Channel Deletion - User Banned", discord.Color.red(), {"User": entry.user.mention, "Channel": channel.name})
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id not in whitelisted:
            await role.guild.ban(entry.user, reason="Unauthorized role deletion")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🛑 Unauthorized Role Deletion - User Banned", discord.Color.red(), {"User": entry.user.mention, "Role": role.name})
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=1):
        if entry.user.id not in whitelisted:
            if after.permissions.administrator and not before.permissions.administrator:
                await after.guild.ban(entry.user, reason="Unauthorized role permission escalation")
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🔐 Unauthorized Admin Permission Given - User Banned", discord.Color.red(), {"User": entry.user.mention, "Role": after.name})
                await log_channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    if member.bot:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id not in whitelisted:
                await member.guild.ban(entry.user, reason="Unauthorized bot addition")
                log_channel = await get_log_channel(member.guild)
                embed = create_log_embed("🤖 Unauthorized Bot Addition - User Banned", discord.Color.red(), {"User": entry.user.mention, "Bot Added": member.mention})
                await log_channel.send(embed=embed)

@bot.command()
async def whitelist(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.add(member.id)
        await ctx.send(f"✅ {member} added to whitelist!")
    else:
        await ctx.send("🚫 Not authorized.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.discard(member.id)
        await ctx.send(f"❌ {member} removed from whitelist!")
    else:
        await ctx.send("🚫 Not authorized.")

bot.run(TOKEN)
