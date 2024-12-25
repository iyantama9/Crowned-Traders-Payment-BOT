import discord
from discord.ext import commands, tasks
import requests
import asyncio
import base64
import time
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()

# Constants and configuration
JSON_FILE_URL = os.getenv('JSON_FILE_URL')
TOKEN = os.getenv('DISCORD_TOKEN')
MIDTRANS_SERVER_KEY = os.getenv('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.getenv('MIDTRANS_CLIENT_KEY')
MIDTRANS_ENDPOINT = os.getenv('MIDTRANS_ENDPOINT')
GUILD_ID = int(os.getenv('GUILD_ID'))
PROJECT_ID = os.getenv('PROJECT_ID')
BUCKET_NAME = os.getenv('BUCKET_NAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Base64 encode the Midtrans server key
encoded_key = base64.b64encode((MIDTRANS_SERVER_KEY + ':').encode()).decode()

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
user_emails = {}
user_names = {}
user_phone_numbers = {}
payment_status = {}
role_expiry = {}
user_members = {}  # Store user ID and name instead of Member objects

# Google Sheets setup
def load_serviceaccount(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

service_account_json = load_serviceaccount(JSON_FILE_URL)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = service_account.Credentials.from_service_account_info(service_account_json, scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)

# Function to write data to Google Sheets
def gsheet(user_id, email, name, phone, role_name, order_id, payment_status, sheet_name):
    values = [
        [user_id, email, name, phone, role_name, order_id, payment_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ]
    body = {'values': values}
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f'{sheet_name}!A1',
        valueInputOption='RAW', body=body).execute()
    print(f"{result.get('updates').get('updatedCells')} cells appended.")

# Registration period and class duration
START_REGISTRATION_DATE = datetime(2024, 12, 25)  
REGISTRATION_PERIOD_DAYS = 7 
CLASS_DURATION_DAYS = 30 

# Calculate end class date
END_CLASS_DATE = START_REGISTRATION_DATE + timedelta(days=CLASS_DURATION_DAYS) 

async def remove_role(guild):
    now = time.time()  
    for user_id, (role, expiry_time) in list(role_expiry.items()):
        if now >= expiry_time:  
            member = guild.get_member(user_id)
            if member and role:
                await member.remove_roles(role)
                print(f"Role {role.name} telah dihapus dari {member.name}")
            del role_expiry[user_id] 

@tasks.loop(hours=24)
async def schedule_role_removal():
    global START_REGISTRATION_DATE, END_CLASS_DATE
    now = datetime.now()
    
    if now >= END_CLASS_DATE: 
        guild = bot.get_guild(GUILD_ID)
        await remove_role(guild)
        
        START_REGISTRATION_DATE = END_CLASS_DATE + timedelta(days=1) 
        END_CLASS_DATE = START_REGISTRATION_DATE + timedelta(days=CLASS_DURATION_DAYS)  
        
        for channel in guild.text_channels:
            await channel.send(f"📅 Pendaftaran untuk kelas baru dibuka! Mulai dari {START_REGISTRATION_DATE.strftime('%d-%m-%Y')} hingga {START_REGISTRATION_DATE + timedelta(days=REGISTRATION_PERIOD_DAYS)}.")

async def function_role(guild, user_id, role_name, duration_days=30):
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(user_id)
    
    if not member:
        print(f"Member dengan ID {user_id} tidak ditemukan di guild {guild.name}.")
        return
    
    if not role:
        print(f"Role '{role_name}' tidak ditemukan di guild {guild.name}.")
        return
    
    bot_member = guild.get_member(bot.user.id)
    bot_top_role = bot_member.top_role
    if role.position >= bot_top_role.position:
        print(f"Role '{role_name}' memiliki posisi di atas atau sama dengan role bot di guild {guild.name}.")
        return
    
    try:
        await member.add_roles(role)
        print(f"Role {role_name} telah ditambahkan ke {member.name} (ID: {member.id})")
        
        expiry_time = time.time() + duration_days * 24 * 60 * 60  
        role_expiry[user_id] = (role, expiry_time)
    except discord.Forbidden:
        print(f"Bot tidak memiliki izin untuk menambahkan role {role_name} ke {member.name} (ID: {member.id}).")
    except discord.HTTPException as e:
        print(f"Terjadi kesalahan saat menambahkan role {role_name} ke {member.name} (ID: {member.id}): {e}")
    except Exception as e:
        print(f"Terjadi kesalahan tidak terduga saat menambahkan role {role_name} ke {member.name} (ID: {member.id}): {e}")

# FastAPI setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test link for the role
test_link = "https://forms.gle/4caBzgzJJhhXsR5L8"

# Discord bot commands
@bot.command()
async def beli(ctx):
    print(f"Perintah !beli dipanggil oleh: {ctx.author.name} (ID: {ctx.author.id})")  

    # Clear previous user data if exists
    if ctx.author.id in user_emails:  
        del user_emails[ctx.author.id]
    if ctx.author.id in user_names:  
        del user_names[ctx.author.id]
    if ctx.author.id in user_phone_numbers:  
        del user_phone_numbers[ctx.author.id]

    now = datetime.now()
    await ctx.send("🎉 **Pembayaran Role**\nHalo! 👋 Silakan masukkan email kamu untuk memulai proses pembayaran:")
    print(f"Pesan email dikirim ke {ctx.author.name} (ID: {ctx.author.id})") 

    user_members[ctx.author.id] = ctx.author.name  # Store only the name

    def check_email(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        email_msg = await bot.wait_for('message', check=check_email, timeout=60.0)
        email = email_msg.content
        if "@" not in email or "." not in email:
            await ctx.send("❌ **Oops!** Masukkan email yang valid, ya!")
            return
        user_emails[ctx.author.id] = email

        await ctx.send("📋 **Masukkan Nama Lengkap**\nSilakan masukkan nama lengkap kamu:")
        print(f"Pesan nama dikirim ke {ctx.author.name} (ID: {ctx.author.id})") 

        def check_name(m):
            return m.author == ctx.author and m.channel == ctx.channel

        name_msg = await bot.wait_for('message', check=check_name, timeout=60.0)
        name = name_msg.content
        user_names[ctx.author.id] = name

        await ctx.send("📞 **Masukkan Nomor Telepon**\nSilakan masukkan nomor telepon kamu:\n*Data kamu akan Yumi gunakan ketika ada kesalahan dalam pembayaran atau sistem kami.*")
        print(f"Pesan nomor telepon dikirim ke {ctx.author.name} (ID: {ctx.author.id})")  

        def check_phone(m):
            return m.author == ctx.author and m.channel == ctx.channel

        phone_msg = await bot.wait_for('message', check=check_phone, timeout=60.0)
        phone = phone_msg.content
        user_phone_numbers[ctx.author.id] = phone

        options = [
            discord.SelectOption(label="THE WARRIORS MONTHLY", value="THE WARRIORS MONTHLY", description="Role buat kamu yang udah bisa trading tapi butuh profile trading harian!!"),
            discord.SelectOption(label="THE FELLOWS MONTHLY", value="THE FELLOWS MONTHLY", description="Role buat kamu yang pengen belajar intensif dari awal sampai bisa trading!!"),
        ]

        select = discord.ui.Select(placeholder="Pilih role yang ingin kamu beli...", options=options)

        async def select_callback(interaction):
            await interaction.response.defer()  # Menunda respons untuk menghindari timeout
            role_name = select.values[0]
            print(f"Role yang dipilih: {role_name}")  # Log role yang dipilih
            
            if role_name == "THE WARRIORS MONTHLY":
                # Send test link and ask for score
                await interaction.followup.send(
                    f"🔗 **Silakan kerjakan tes berikut untuk mendapatkan akses ke role '{role_name}':**\n{test_link}\n\n**Masukkan nilai kamu (0-100):**"
                )

                def check_score(m):
                    return m.author == ctx.author and m.channel == ctx.channel

                try:
                    score_msg = await bot.wait_for('message', check=check_score, timeout=60.0)
                    score = int(score_msg.content)
                    print(f"Nilai yang dimasukkan: {score}") 

                    if score < 80:
                        await interaction.followup.send(
                            "❌ **Nilai kamu tidak cukup untuk mendapatkan role 'THE WARRIORS MONTHLY'.**\n\n🔍 **Silakan pilih role 'THE FELLOWS MONTHLY':**"
                        )
                        return 
                    
                    else:
                        # Proceed to payment for THE WARRIORS MONTHLY
                        await interaction.followup.send(
                            f"🎊 **Selamat!** Nilai kamu cukup untuk mendapatkan role '{role_name}'.\n\nSilakan lakukan pembayaran di sini:"
                        )
                        
                        try:
                            # Call the process_payment function to handle the payment
                            await process_payment(interaction, "THE WARRIORS MONTHLY", email, name, phone, select)
                        except Exception as e:
                            print(f"Terjadi kesalahan saat memproses pembayaran untuk {interaction.user.name} (ID: {interaction.user.id}): {e}")
                            await interaction.followup.send("❌ **Kesalahan**\nTerjadi kesalahan saat memproses pembayaran. Silakan coba lagi nanti.", ephemeral=True)

                except ValueError:
                    await interaction.followup.send("❌ **Masukkan nilai yang valid (0-100).**")
                    return
                except asyncio.TimeoutError:
                    await interaction.followup.send("⏰ **Waktu habis! Silakan coba lagi.**")
                    return
                
            elif role_name == "THE FELLOWS MONTHLY":
                await process_payment(interaction, "THE FELLOWS MONTHLY", email, name, phone, select)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await ctx.send("🔍 **Pilih Role**\nSilakan pilih role yang ingin kamu beli:", view=view)

    except asyncio.TimeoutError:
        await ctx.send("⏰ **Waktu Habis**\nWaktu habis! Silakan coba lagi dengan `!beli`.")

async def process_payment(interaction, role_name, email, name, phone, select):
    order_id = f'order-{interaction.user.id}-{int(time.time())}'
    print(f"Email: {email}, Name: {name}, Phone: {phone}")

    price = 150000
    payload = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": price
        },
        "item_details": [{
            "id": "item-123",
            "price": price,
            "quantity": 1,
            "name": role_name
        }],
        "customer_details": {
            "first_name": interaction.user.name,
            "email": email
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_key}"
    }

    try:
        response = requests.post(MIDTRANS_ENDPOINT, json=payload, headers=headers)
        print(f"Midtrans response: {response.json()}") 
        response.raise_for_status()
        payment_url = response.json().get('redirect_url')

        if payment_url:
            # Disable previous payment link if exists
            for oid in payment_status.keys():
                if payment_status[oid]['user_id'] == interaction.user.id:
                    payment_status[oid]['status'] = 'canceled'  # Mark previous order as canceled

            payment_status[order_id] = {'status': 'pending', 'role': role_name, 'user_id': interaction.user.id}

            # Create the payment button
            button = discord.ui.Button(label="💳 Bayar di sini", url=payment_url, style=discord.ButtonStyle.success)
            view = discord.ui.View()
            view.add_item(button)

            # Send the payment message with the button
            await interaction.followup.send(
                f"🎊 **Pembayaran Diperlukan**\nSilakan lakukan pembayaran di sini:",
                view=view,
                ephemeral=True
            )

            # Disable the original select dropdown if payment is initiated
            select.disabled = True  # Disable the original select dropdown
            await interaction.message.edit(view=view)  

        else:
            await interaction.followup.send("❌ **Kesalahan**\nTerjadi kesalahan saat membuat pembayaran. Tidak ada URL pembayaran yang diterima.", ephemeral=True)
    except requests.exceptions.RequestException as e:
        await interaction.followup.send("❌ **Kesalahan**\nTerjadi kesalahan saat menghubungi Midtrans API. Coba lagi nanti, ya!", ephemeral=True)
        print(f"Error: {e}")
        print(f"Response: {response.text}")

# FastAPI payment notification endpoint
@app.post('/payment-notification')
async def payment_notification(request: Request):
    data = await request.json()
    
    if 'order_id' in data and 'transaction_status' in data:
        order_id = data['order_id']
        transaction_status = data['transaction_status']
        
        print(f"Received order_id: {order_id}")
        print(f"Transaction status: {transaction_status}")
        
        if order_id in payment_status:
            if transaction_status in ['settlement', 'capture']:
                user_id = order_id.split('-')[1]
                guild = bot.get_guild(GUILD_ID)
                role_name = payment_status[order_id]['role']
                
                # Call function_role to add the role
                bot.loop.create_task(function_role(guild, int(user_id), role_name))
                
                payment_status[order_id]['status'] = 'settled'
                print(f"Update payment status for order_id {order_id}: settled")
                
                user = await bot.fetch_user(payment_status[order_id]['user_id'])
                await user.send(f"✅ **Pembayaran Berhasil**\nPembayaran untuk order ID `{order_id}` telah berhasil! Role `{role_name}` telah ditambahkan")
                
                email = user_emails.get(int(user_id))
                name = user_names.get(int(user_id))
                phone = user_phone_numbers.get(int(user_id))
                sheet_name = 'FELLOWS' if role_name == "THE FELLOWS MONTHLY" else 'WARRIORS'
                gsheet(user_id, email, name, phone, role_name, order_id, 'settled', sheet_name)
                
                return JSONResponse(content={"status": "success"})
        else:
            print(f"Order ID {order_id} not found in payment_status.")
    
    return JSONResponse(content={"status": "ignored"})

@bot.event
async def on_ready():
    load_data()  # Load data when the bot is ready
    print(f"Bot telah siap sebagai {bot.user.name} (ID: {bot.user.id})")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f"Bot berada di guild: {guild.name} (ID: {guild.id})")
    else:
        print(f"Bot tidak berada di guild dengan ID {GUILD_ID}")

    # Print loaded data for verification
    print("Data yang dimuat dari JSON:")
    print("User Emails:", user_emails)
    print("User Names:", user_names)
    print("User Phone Numbers:", user_phone_numbers)
    print("Payment Status:", payment_status)
    print("Role Expiry:", role_expiry)
    print("User Members:", user_members)

@bot.command()
async def closechannel(ctx):
    try:
        channel = ctx.channel
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send('Anda tidak memiliki izin untuk menutup channel.')
            return
        
        await ctx.send('Channel akan segera ditutup.')
        
        await channel.delete(reason='Channel ditutup oleh bot')
    
    except discord.Forbidden:
        await ctx.send('Bot tidak memiliki izin untuk menghapus channel.')
    except discord.HTTPException as e:
        await ctx.send(f'Terjadi kesalahan: {e}')

@bot.command()
async def checkpay(ctx):
    """Command to check payment status."""
    user_id = ctx.author.id
    user_payments = {oid: status for oid, status in payment_status.items() if status['user_id'] == user_id}

    if not user_payments:
        await ctx.send("❌ **Tidak ada pembayaran yang ditemukan untuk Anda.**")
        return

    response = "📜 **Status Pembayaran Anda:**\n"
    for order_id, status in user_payments.items():
        response += f"**Order ID:** {order_id} - **Status:** {status['status']}\n"

    await ctx.send(response)

# Function to save data to a JSON file
def save_data():
    data = {
        "user_emails": user_emails,
        "user_names": user_names,
        "user_phone_numbers": user_phone_numbers,
        "payment_status": payment_status,
        "role_expiry": {user_id: (role.name if role else None, expiry_time) for user_id, (role, expiry_time) in role_expiry.items()},  # Store role names instead of Role objects
        "user_members": {user_id: name for user_id, name in user_members.items()},  # Store only names
    }
    with open('data.json', 'w') as f:
        json.dump(data, f)

# Function to load data from a JSON file
def load_data():
    global user_emails, user_names, user_phone_numbers, payment_status, role_expiry, user_members
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
            user_emails = data.get("user_emails", {})
            user_names = data.get("user_names", {})
            user_phone_numbers = data.get("user_phone_numbers", {})
            payment_status = data.get("payment_status", {})
            role_expiry = {user_id: (discord.utils.get(bot.get_guild(GUILD_ID).roles, name=role_name), expiry_time) for user_id, (role_name, expiry_time) in data.get("role_expiry", {}).items()}  # Load roles by name
            user_members = data.get("user_members", {})  # Load names only
            
            # Print loaded data for verification
            print("Data yang dimuat dari JSON:")
            print("User Emails:", user_emails)
            print("User Names:", user_names)
            print("User Phone Numbers:", user_phone_numbers)
            print("Payment Status:", payment_status)
            print("Role Expiry:", role_expiry)
            print("User Members:", user_members)

    except FileNotFoundError:
        print("Data file not found. Starting with empty data.")
    except json.JSONDecodeError:
        print("Error decoding JSON data. Starting with empty data.")

# FastAPI server startup
async def start_fastapi():
    port = int(os.getenv('PORT', 8080)) 
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# Main function to run the bot and FastAPI
async def main():
    schedule_role_removal.start()
    fastapi_task = asyncio.create_task(start_fastapi())
    await bot.start(TOKEN)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
        save_data() 