import asyncio
import websockets
from util.power_trace import generate, noise
from util.prompts import *
import json
import random

def server_log(message):
    print(message,flush=True)

def generate_password(length):
    password = ''
    for _ in range(length):
        password += chr(0x41 + random.randint(0, 25))
    return password

def calc_slice_index(x):
    return int((x - 10) // 5)

def generate_trace(guess, actual):
    step = 0.01
    x = 0
    x_s, y_s = [], []
    incorrect = False
    while x < 10 + (5 * len(actual)):
        if x >= 10:
            # Check characters.
            slice_index = calc_slice_index(x)
            
            # If we previously determined it to be incorrect,
            # Add a zero.
            if incorrect:
                x_s.append(x)
                y_s.append(noise(0, 0.5))
                x += step
                continue
            
            # If the current value is incorrect, report it until we hit the next slice
            if guess[slice_index] != actual[slice_index]:
                incorrect = True
                while calc_slice_index(x) < slice_index + 1:
                    x_s.append(x)
                    y_s.append(generate(x, guess, actual))
                    x += step
        
        x_s.append(x)
        y_s.append(generate(x, guess, actual))
        x += step
    
    return x_s, y_s

async def server_main(websocket):
    # Generate a random password.
    g_Password = generate_password(5)
    g_CorrectGuess = False

    # Only allow k * n (characters * slots) + 25 attempts.
    g_MaxAttempts = 26 * len(g_Password) + 25
    g_CurrentAttempts = 0

    # Send boot logs.
    await websocket.send(json.dumps({
        'kind': 'boot',
        'content' : uboot_logs_1() + uboot_logs_2() + uboot_logs_3() + logo() + 'Enter password (5 characters, ALPHABETICAL...):'
    }))  

    try:
        while g_CurrentAttempts < g_MaxAttempts and not g_CorrectGuess:
            server_log(f'Waiting for guess...')
            password_guess = await asyncio.wait_for(websocket.recv(), timeout=120)
            server_log(f'Guessed: {password_guess}')
            server_log(f'Actual: {g_Password}')

            # If the lengths aren't the same, don't send any trace data.
            if len(password_guess) != len(g_Password):
                await websocket.send(json.dumps({
                    'kind' : 'password',
                    'is_correct' : False,
                    'reason' : 'wrong_character_count',
                    'content' : f'Incorrect password "{password_guess}". Try again: '
                }))
                continue
            
            # If they are, check if the password is right (and send the respective trace data).
            x, y = generate_trace(password_guess, g_Password)
            if password_guess != g_Password:
                server_log('Incorrect guess.')
                await websocket.send(json.dumps({
                    'kind' : 'password',
                    'is_correct' : False,
                    'reason' : 'no_match',
                    'trace' : {
                        'x' : x,
                        'y' : y
                    },
                    'content' : f'Incorrect password "{password_guess}". Try again: '
                }))
                continue
            
            # If the guess is right, send the flag.
            if password_guess == g_Password:
                g_CorrectGuess = True
                with open('flag.txt') as FLAG:
                    flag = FLAG.readline()
                    await websocket.send(json.dumps({
                        'kind' : 'password',
                        'is_correct' : True,
                        'trace' : {
                            'x' : x,
                            'y' : y
                        },
                        'content' : f'Login successful!\nMessage of the day: {flag}'
                    }))
        await websocket.close()
    except websockets.exceptions.ConnectionClosed as e:
        server_log(f"[!] Connection was closed.")

async def main():
    server_log("Server started on ws://0.0.0.0:6789")
    async with websockets.serve(server_main, "0.0.0.0", 6789, ping_timeout=120):
        await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
