import argparse, json, os, subprocess, sys, shutil, time, stat
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[ForgeBuild] %(levelname)s: %(message)s'
)
logger = logging.getLogger("ForgeBuild")

def load_config():
    try:
        with open("forgebuild.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("forgebuild.json not found.")
        sys.exit(1)

def init_project():
    if os.path.exists("forgebuild.json"):
        logger.warning("Project already initialized.")
        return

    default = {
        "targets": {
            "app": {
                "sources": ["src/main.cpp"],
                "output": "build/app.exe",
                "compiler": "clang++",
                "flags": ["-Wall", "-Iinclude"]
            }
        },
        "dependencies": {}
    }

    os.makedirs("src", exist_ok=True)
    os.makedirs("include", exist_ok=True)
    os.makedirs("build", exist_ok=True)

    with open("forgebuild.json", "w") as f:
        json.dump(default, f, indent=4)
    logger.info("Project initialized with default config.")

    main_cpp = """#include <iostream>

int main() {
    std::cout << "Hello, world!" << std::endl;
    return 0;
}
"""
    with open("src/main.cpp", "w") as f:
        f.write(main_cpp)
    logger.info("Default src/main.cpp created.")

    script_path = os.path.abspath(sys.argv[0])
    launcher = f"""\n# ForgeBuild launcher script
# Usage: .\\forgebuild.ps1 --build (or any other supported ForgeBuild arguments!)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath
echo 'running forgebuild wrapper v1.0...'
echo 'forgebuild is located at: {script_path}'
py "{script_path}" @args
"""
    with open("forgebuild.ps1", "w") as f:
        f.write(launcher)
    logger.info("Project setup complete!")

def check_compilers():
    clang_path = shutil.which("clang++")
    gpp_path = shutil.which("g++")
    return clang_path, gpp_path

def run_diagnostics():
    config = load_config()
    if "targets" not in config or not config["targets"]:
        logger.warning("No targets defined.")
    else:
        logger.info("OK: Targets found: " + ", ".join(config["targets"].keys()))
    if not os.path.exists("src"):
        logger.warning("src/ folder missing.")
    if not os.path.exists("include"):
        logger.warning("include/ folder missing.")
    fndc, fndg = check_compilers()
    if fndc:
        logger.info("OK: found clang++!")
    if fndg:
        logger.info("OK: found g++!")
    if not fndc:
        logger.critical("clang++ was NOT found!")
    if not fndg:
        logger.warning("g++ was NOT found!")
    if not fndg and not fndc:
        logger.critical("no compatible compilers were found!")
    logger.info("Diagnostics complete.")

def unlock_folder(path):
    for root, dirs, files in os.walk(path):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                os.chmod(fpath, stat.S_IWRITE)
            except Exception:
                pass

def sync_dependencies(force=False):
    config = load_config()
    deps = config.get("dependencies", {})
    if not deps:
        logger.info("No dependencies to sync.")
        return

    os.makedirs("include", exist_ok=True)

    for name, info in deps.items():
        repo = info["repo"]
        branch = info.get("branch", "main")
        target_dir = os.path.join("include", name)

        if os.path.exists(target_dir) and not force:
            logger.info(f"Skipping {name}: already installed at {target_dir}")
            continue

        if os.path.exists(target_dir):
            logger.warning(f"Removing existing {target_dir}...")
            try:
                unlock_folder(target_dir)
                shutil.rmtree(target_dir)
            except Exception as e:
                logger.error(f"Could not remove {target_dir}: {e}")
                logger.warning("Please delete the folder manually or use --force-sync")
                continue

        logger.info(f"Syncing {name} from {repo} ({branch})")
        subprocess.run(["gh", "repo", "clone", repo, target_dir])

        result = subprocess.run(["git", "-C", target_dir, "checkout", branch], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Could not checkout branch '{branch}'")
            logger.error(result.stderr.strip())
            continue

        logger.info(f"{name} synced to include/{name}")

def build_project(verbose=False):
    config = load_config()
    target = list(config["targets"].keys())[0]
    tconf = config["targets"][target]

    compiler = tconf["compiler"]
    if compiler == 'g++':
        logger.warning("g++ support is EXPERIMENTAL and is NOT recommended for production!")
    elif compiler == "clang":
        logger.critical("if you were intending to use clang (thinking it was an alias for clang++) it is NOT. please rebuild with clang++!")
        return
    flags = tconf["flags"][:]
    if verbose and "-v" not in flags:
        flags.append("-v")
    sources = tconf["sources"]
    output = tconf["output"]

    cmd = [compiler] + flags + sources + ["-o", output]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    logger.info("stdout:\n" + (result.stdout or " [empty]"))
    logger.info("stderr:\n" + (result.stderr or " [empty]"))

    if result.returncode == 0:
        logger.info(f"Build succeeded: {output}")
    else:
        logger.error(f"Build failed with code {result.returncode}")

def main():
    parser = argparse.ArgumentParser(description="ForgeBuild 2.4 — Python Build System for C++")
    parser.add_argument("--init", action="store_true", help="Initialize a new project")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--build", action="store_true", help="Build your project")
    parser.add_argument("--sync", action="store_true", help="Sync dependencies from GitHub")
    parser.add_argument("--force-sync", action="store_true", help="Force re-sync of all dependencies")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose compiler output")

    args = parser.parse_args()

    if not any(vars(args).values()):
        logger.info("HINT: if you were trying to build, you now need to run forgebuild --build")
        return

    if args.init:
        init_project()
    if args.check:
        run_diagnostics()
    if args.sync:
        sync_dependencies(force=args.force_sync)
    if args.build:
        build_project(verbose=args.verbose)

if __name__ == "__main__":
    main()