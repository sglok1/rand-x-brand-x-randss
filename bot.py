import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}
LINK_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

# Security Settings
PUNISHMENT_DURATION = timedelta(days=1)  # 1 day timeout
BOT_PROTECTION = True
ANTI_LINKS = True
ANTI_SPAM = True
ANTI_RAID = True

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

# ========================
# CHANNEL PROTECTION SYSTEM
# ========================
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id not in whitelisted:
            await channel.delete()
            await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized channel creation")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚨 CHANNEL CREATION BANNED", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED + Channel Deleted",
                "Channel": channel.name,
                "Reason": "Unauthorized channel creation"
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized channel deletion")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚨 CHANNEL DELETION BANNED", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Channel": channel.name,
                "Reason": "Unauthorized channel deletion"
            })
            await log_channel.send(embed=embed)

# ====================
# ROLE PROTECTION SYSTEM
# ====================
@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id not in whitelisted:
            await role.delete()
            await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized role creation")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚨 ROLE CREATION BANNED", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED + Role Deleted",
                "Role": role.name,
                "Reason": "Unauthorized role creation"
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized role deletion")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚨 ROLE DELETION BANNED", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Role": role.name,
                "Reason": "Unauthorized role deletion"
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized role modification")
            log_channel = await get_log_channel(after.guild)
            embed = create_log_embed("🚨 ROLE MODIFICATION BANNED", discord.Color.red(), {
                "User": f"{entry.user} ({entry.user.id})",
                "Action": "BANNED",
                "Role": after.name,
                "Changes": f"Permissions: {before.permissions.value} → {after.permissions.value}",
                "Reason": "Unauthorized role modification"
            })
            await log_channel.send(embed=embed)

# ========================
# ROLE ASSIGNMENT PROTECTION
# ========================
@bot.event
async def on_member_update(before, after):
    # Role assignment check
    added_roles = [role for role in after.roles if role not in before.roles]
    if added_roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            if entry.user.id not in whitelisted and entry.user != after:
                # Punish the assigner
                await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized role assignment")
                
                # Punish the receiver
                for role in added_roles:
                    await after.remove_roles(role, reason="Unauthorized role assignment")
                try:
                    await after.timeout(PUNISHMENT_DURATION, reason="Received unauthorized roles")
                except:
                    pass
                
                # Log the action
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🚨 UNAUTHORIZED ROLE ASSIGNMENT", discord.Color.red(), {
                    "Assigner": f"{entry.user} ({entry.user.id}) [BANNED]",
                    "Target": f"{after} ({after.id}) [TIMEOUT + ROLES REMOVED]",
                    "Roles": ', '.join([role.name for role in added_roles]),
                    "Reason": "Unauthorized role assignment"
                })
                await log_channel.send(embed=embed)

# =================
# BOT PROTECTION SYSTEM
# =================
@bot.event
async def on_member_join(member):
    if member.bot and BOT_PROTECTION:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id not in whitelisted:
                # Ban the inviter
                await entry.user.ban(reason="🚨 Auto-Ban: Unauthorized bot addition")
                
                # Kick the bot
                await member.kick(reason="Unauthorized bot")
                
                # Log the action
                log_channel = await get_log_channel(member.guild)
                embed = create_log_embed("🚨 UNAUTHORIZED BOT ADDED", discord.Color.red(), {
                    "Inviter": f"{entry.user} ({entry.user.id}) [BANNED]",
                    "Bot": f"{member} ({member.id}) [KICKED]",
                    "Reason": "Unauthorized bot addition"
                })
                await log_channel.send(embed=embed)

# ================
# ANTI-LINK SYSTEM
# ================
@bot.event
async def on_message(message):
    if ANTI_LINKS and not message.author.bot and message.author.id not in whitelisted:
        if LINK_PATTERN.search(message.content):
            try:
                await message.delete()
                await message.author.timeout(PUNISHMENT_DURATION, reason="Sending links")
                
                log_channel = await get_log_channel(message.guild)
                embed = create_log_embed("🚨 LINK DETECTED", discord.Color.orange(), {
                    "User": f"{message.author} ({message.author.id})",
                    "Action": "MESSAGE DELETED + TIMEOUT",
                    "Channel": message.channel.mention,
                    "Reason": "Unauthorized link sharing"
                })
                await log_channel.send(embed=embed)
            except:
                pass
    
    await bot.process_commands(message)

# ================
# WHITELIST SYSTEM
# ================
@bot.command()
@commands.is_owner()
async def whitelist(ctx, member: discord.Member):
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
    whitelisted.discard(member.id)
    await ctx.send(f"❌ {member} has been removed from the whitelist!")
    log_channel = await get_log_channel(ctx.guild)
    embed = create_log_embed("❌ WHITELIST REMOVED", discord.Color.red(), {
        "User": f"{member} ({member.id})",
        "Action": "Removed from whitelist",
        "By": ctx.author.mention
    })
    await log_channel.send(embed=embed)

@bot.command()
@commands.is_owner()
async def whitelist_show(ctx):
    members = []
    for user_id in whitelisted:
        user = bot.get_user(user_id)
        members.append(f"{user.mention if user else 'Unknown user'} (ID: {user_id})")
    
    embed = discord.Embed(title="🔐 Whitelisted Users", color=discord.Color.blue())
    embed.description = "\n".join(members) if members else "No whitelisted users"
    await ctx.send(embed=embed)

# ================
# SECURITY SETTINGS
# ================
@bot.command()
@commands.is_owner()
async def security_settings(ctx):
    embed = discord.Embed(title="🔒 Security Settings", color=discord.Color.blue())
    embed.add_field(name="Bot Protection", value="✅ Enabled" if BOT_PROTECTION else "❌ Disabled", inline=False)
    embed.add_field(name="Anti-Link", value="✅ Enabled" if ANTI_LINKS else "❌ Disabled", inline=False)
    embed.add_field(name="Anti-Spam", value="✅ Enabled" if ANTI_SPAM else "❌ Disabled", inline=False)
    embed.add_field(name="Anti-Raid", value="✅ Enabled" if ANTI_RAID else "❌ Disabled", inline=False)
    embed.add_field(name="Punishment Duration", value=str(PUNISHMENT_DURATION), inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
