import sys
import os
import subprocess

def main():
    """Launcher entry point for GEXOR Streamlit Dashboard."""
    print("Launching GEXOR Gamma Exposure Dashboard...")
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", app_path]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
