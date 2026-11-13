import argparse
import subprocess
import sys
from database.store import initialize, get_agents

def main():
    parser = argparse.ArgumentParser(description="Trading Agent Lab CLI")
    parser.add_argument("command", choices=["dashboard", "status", "test"])
    args = parser.parse_args()
    initialize()

    if args.command == "dashboard":
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            check=True,
        )
    elif args.command == "status":
        for agent in get_agents():
            print(f'{agent["name"]}: {agent["status"]} — {agent["responsibility"]}')
    elif args.command == "test":
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        raise SystemExit(result.returncode)

if __name__ == "__main__":
    main()
