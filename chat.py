import time
from agent import handle

EXIT = {"exit", "quit", "keluar", "selesai", "/exit", "/quit", "/keluar", "q"}
run = int(time.time())
n = 0
print("Ketik pesan, atau 'foto:images/15.jpg'. Keluar: ketik 'exit' atau 'keluar' (atau Ctrl+D).\n")
while True:
    try:
        t = input("kamu> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSampai jumpa.")
        break
    if t.lower() in EXIT:
        print("Sampai jumpa.")
        break
    if not t:
        continue
    n += 1
    mid = f"run{run}-{n}"
    try:
        if t.startswith("foto:"):
            r = handle("cli", "me", mid, "photo", image=open(t[5:], "rb").read())
        else:
            r = handle("cli", "me", mid, "text", text=t)
    except FileNotFoundError:
        r = "File foto tidak ditemukan."
    print("\nBOT>", r, "\n")
