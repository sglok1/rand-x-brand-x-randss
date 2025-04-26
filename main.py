import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
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

# Protection systems
message_count = defaultdict(list)
BACKUP_FILE = "server_backup.json"
PUNISHMENT_DURATION = timedelta(days=1)  # 1 day timeout

# Backup Data
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
        log_channel = await guild.create_text_channel(
            "security-logs",
            overwrites=overwrites,
            reason="Automatic log channel creation"
        )
    return log_channel

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (Security Mode: MAXIMUM)')
    for guild in bot.guilds:
        await get_log_channel(guild)
        await backup_server_data(guild)
    auto_backup.start()

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
@commands.is_owner()
async def restore(ctx):
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

# ========================
# ENHANCED WHITELIST SYSTEM
# ========================
@bot.command()
@commands.is_owner()
async def whitelist_show(ctx):
    """Show all whitelisted users"""
    members = []
    for user_id in whitelisted:
        user = bot.get_user(user_id)
        members.append(f"{user.mention if user else 'Unknown user'} (ID: {user_id})")
    
    embed = discord.Embed(title="🔐 Whitelisted Users", color=discord.Color.blue())
    embed.description = "\n".join(members) if members else "No whitelisted users"
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def whitelist(ctx, member: discord.Member):
    """Add user to whitelist"""
    whitelisted.add(member.id)
    await ctx.send(f"✅ {member} has been added to the whitelist!")
    log_channel = await get_log_channel(ctx.guild)
    embed = create_log_embed("✅ WHITELIST ADDED", discord.Color.green(), {
        "User": f"{member} ({member.id})",
        "Action": "Added to whitelist",
        "By": ctx.author.mention
    })
    await log_channel.send(embed=embed)

@bot.command()
@commands.is_owner()
async def whitelist_remove(ctx, member: discord.Member):
    """Remove user from whitelist"""
    whitelisted.discard(member.id)
    await ctx.send(f"❌ {member} has been removed from the whitelist!")
    log_channel = await get_log_channel(ctx.guild)
    embed = create_log_embed("❌ WHITELIST REMOVED", discord.Color.red(), {
        "User": f"{member} ({member.id})",
        "Action": "Removed from whitelist",
        "By": ctx.author.mention
    })
    await log_channel.send(embed=embed)

# ========================
# ENHANCED SECURITY SYSTEMS
# ========================
@bot.event
async def on_member_update(before, after):
    """Enhanced role assignment protection"""
    # Check for role additions
    added_roles = [role for role in after.roles if role not in before.roles]
    if added_roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            if entry.user.id not in whitelisted and entry.user != after:
                # Ban the user who assigned the roles
                await entry.user.ban(reason="Unauthorized role assignment")
                
                # Remove the added roles from the target user
                for role in added_roles:
                    await after.remove_roles(role, reason="Unauthorized role assignment")
                
                # Timeout the user who received the roles (1 day timeout)
                try:
                    await after.timeout(PUNISHMENT_DURATION, reason="Received unauthorized roles")
                except discord.Forbidden:
                    pass
                
                # Log the action
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🚨 Unauthorized Role Assignment", discord.Color.red(), {
                    "Assigner": f"{entry.user} ({entry.user.id}) [BANNED]",
                    "Target": f"{after} ({after.id}) [TIMEOUT + ROLES REMOVED]",
                    "Roles": ', '.join([role.name for role in added_roles]),
                    "Reason": "Unauthorized role assignment"
                })
                await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    """Enhanced role modification protection"""
    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized role modification")
            log_channel = await get_log_channel(after.guild)
            embed = create_log_embed("🚨 Unauthorized Role Modification", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Role": after.name,
                "Changes": f"Permissions: {before.permissions.value} → {after.permissions.value}",
                "Reason": "Unauthorized role modification"
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_member_ban(guild, user):
    """Enhanced ban protection"""
    async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
        if entry.user.id not in whitelisted:
            member = guild.get_member(entry.user.id)
            if member:
                await member.edit(roles=[])
                await member.kick(reason="Unauthorized ban attempt")
                log_channel = await get_log_channel(guild)
                embed = create_log_embed("🚨 Unauthorized Ban Attempt", discord.Color.red(), {
                    "User": f"{entry.user} ({entry.user.id}) [KICKED]",
                    "Target": f"{user} ({user.id})",
                    "Action": "Kicked + Roles Cleared",
                    "Reason": "Unauthorized ban attempt"
                })
                await log_channel.send(embed=embed)

@bot.event
async def on_message(message):
    """Enhanced message protection system"""
    if message.author.bot:
        return

    # Spam protection
    uid = message.author.id
    now = datetime.utcnow().timestamp()
    message_count[uid].append(now)
    message_count[uid] = [t for t in message_count[uid] if now - t < 5]

    if len(message_count[uid]) > 5 and uid not in whitelisted:
        await mute_user(message.author)
        log_channel = await get_log_channel(message.guild)
        embed = create_log_embed("⚠️ User Muted for Spamming", discord.Color.orange(), {
            "User": message.author.mention,
            "Count": f"{len(message_count[uid])} messages/5s",
            "Action": "Muted"
        })
        await log_channel.send(embed=embed)

    # Anti-link protection
    if LINK_PATTERN.search(message.content) and message.author.id not in whitelisted:
        await message.delete()
        try:
            await message.author.timeout(timedelta(minutes=10), reason="Link posting")
        except:
            pass
        log_channel = await get_log_channel(message.guild)
        embed = create_log_embed("🚫 Link Detected", discord.Color.orange(), {
            "User": message.author.mention,
            "Action": "Message deleted + timeout",
            "Channel": message.channel.mention
        })
        await log_channel.send(embed=embed)

    # Mass mention protection
    if ("@everyone" in message.content or "@here" in message.content) and message.author.id not in whitelisted:
        try:
            await message.author.timeout(timedelta(hours=1), reason="Mass mention")
            await message.delete()
            log_channel = await get_log_channel(message.guild)
            embed = create_log_embed("🚷 Mass Mention Detected", discord.Color.red(), {
                "User": message.author.mention,
                "Action": "Timeout + message deleted",
                "Duration": "1 hour"
            })
            await log_channel.send(embed=embed)
        except:
            pass

    await bot.process_commands(message)

async def mute_user(member):
    """Mute a user by adding Muted role"""
    guild = member.guild
    muted = discord.utils.get(guild.roles, name="Muted")
    if not muted:
        muted = await guild.create_role(name="Muted")
        for channel in guild.channels:
            await channel.set_permissions(muted, send_messages=False)
    await member.add_roles(muted)

# ========================
# CHANNEL AND ROLE PROTECTION
# ========================
@bot.event
async def on_guild_channel_create(channel):
    """Auto-ban for unauthorized channel creation"""
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id not in whitelisted:
            await channel.delete()
            await entry.user.ban(reason="Unauthorized channel creation")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚨 Unauthorized Channel Created", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED + Channel deleted",
                "Channel": channel.name
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    """Auto-ban for unauthorized channel deletion"""
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized channel deletion")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚨 Unauthorized Channel Deleted", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Channel": channel.name
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_create(role):
    """Auto-ban for unauthorized role creation"""
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id not in whitelisted:
            await role.delete()
            await entry.user.ban(reason="Unauthorized role creation")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚨 Unauthorized Role Created", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED + Role deleted",
                "Role": role.name
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    """Auto-ban for unauthorized role deletion"""
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized role deletion")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚨 Unauthorized Role Deleted", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Role": role.name
            })
            await log_channel.send(embed=embed)

# ========================
# BOT PROTECTION SYSTEM
# ========================
@bot.event
async def on_member_join(member):
    """Auto-ban for unauthorized bot additions"""
    if member.bot:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id not in whitelisted:
                await entry.user.ban(reason="Unauthorized bot addition")
                await member.kick(reason="Unauthorized bot")
                log_channel = await get_log_channel(member.guild)
                embed = create_log_embed("🤖 Unauthorized Bot Added", discord.Color.red(), {
                    "Inviter": f"{entry.user} ({entry.user.id}) [BANNED]",
                    "Bot": f"{member} ({member.id}) [KICKED]"
                })
                await log_channel.send(embed=embed)

bot.run(TOKEN)
