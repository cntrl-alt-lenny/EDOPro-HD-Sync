import os
import sys
import platform
import subprocess

# Define the file path on your Desktop
desktop_path = os.path.expanduser("~/Desktop")
output_file = os.path.join(desktop_path, "diagnostic_log.txt")

def log(message=""):
    """Writes a message to the file and prints a dot to the screen to show progress."""
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(".", end="", flush=True) # Print a dot to show it's working

# Clear the file if it already exists
with open(output_file, "w", encoding="utf-8") as f:
    f.write("")

print(f"Generating diagnostic report at: {output_file}")
print("Please wait", end="")

log("="*40)
log("     LEO'S SYSTEM DIAGNOSTIC")
log("="*40)

# 1. System Info
log(f"\n[SYSTEM]")
log(f"OS: {platform.system()} {platform.release()}")
log(f"Machine: {platform.machine()}")
log(f"Python: {sys.version}")
log(f"Executable: {sys.executable}")

# 2. Directory Info
cwd = os.getcwd()
log(f"\n[DIRECTORY]")
log(f"Current Folder: {cwd}")
log(f"Contents:")
try:
    for item in os.listdir(cwd):
        if item.startswith("."): continue 
        log(f"  - {item}")
except Exception as e:
    log(f"  Error listing directory: {e}")

# 3. Game File Check
log(f"\n[GAME FILES CHECK]")
db_path = os.path.join(cwd, "cards.cdb")
if os.path.exists(db_path):
    size = os.path.getsize(db_path)/1024/1024
    log(f"✅ cards.cdb FOUND (Size: {size:.2f} MB)")
else:
    log(f"❌ cards.cdb NOT FOUND (Normal for Dev folder)")

# 4. Pip Check
log(f"\n[INSTALLED PACKAGES]")
try:
    import pkg_resources
    for d in pkg_resources.working_set:
        log(f"  - {d.project_name} ({d.version})")
except ImportError:
    log("  (Could not list packages via pkg_resources)")
except Exception as e:
    log(f"  Error listing packages: {e}")

log("\n" + "="*40)
log("DIAGNOSTIC COMPLETE")
log("="*40)

print("\nDone! Please upload 'diagnostic_log.txt' from your Desktop.")