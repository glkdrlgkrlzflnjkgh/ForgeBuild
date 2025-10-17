import argparse, json, os, subprocess, sys, shutil, stat, hashlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[ForgeBuild] %(levelname)s: %(message)s'
)
logger = logging.getLogger("ForgeBuild")

CACHE_PATH = ".forgebuild/cache.json"

def hash_file(path):
    with open(path, "rb") as f:

        return hashlib.sha256(f.read()).hexdigest()

def load_config():
    try:
        with open("forgebuild.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("forgebuild.json not found.")
        sys.exit(1)

def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    os.makedirs(".forgebuild", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=4)

def build_project(verbose=False, use_cache=False):
    config = load_config()
    cache = load_cache() if use_cache else {}
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

    os.makedirs(".forgebuild/cache", exist_ok=True)
    object_files = []
    rebuild_needed = False

    for src in sources:
        obj = os.path.join(".forgebuild", "cache", os.path.basename(src).replace(".cpp", ".o"))
        object_files.append(obj)

        src_hash = hash_file(src)
        cached_hash = cache.get(src)

        if verbose:
            logger.info(f"Current hash: {src_hash}")
            logger.info(f"Cached hash: {cache.get(src)}")

        if not use_cache or cached_hash != src_hash or not os.path.exists(obj):
            rebuild_needed = True
            if not use_cache:
                logger.info("--force-rebuild was probably passed. Rebuilding...")
            logger.info(f"Compiling {src} -> {obj}")
            cmd = [compiler] + flags + ["-c", src, "-o", obj]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.info("stdout:\n" + (result.stdout or " [empty]"))
            logger.info("stderr:\n" + (result.stderr or " [empty]"))
            if result.returncode != 0:
                logger.error(f"Compilation failed for {src}")
                return
            cache[src] = src_hash
        else:
            logger.info(f"Skipping compile of {src} — no changes detected.")

    if not rebuild_needed and use_cache:
        logger.info("Skipping link — no changes detected.")
        return

    logger.info(f"Linking: {' '.join(object_files)} -> {output}")
    cmd = [compiler] + object_files + ["-o", output]
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info("stdout:\n" + (result.stdout or " [empty]"))
    logger.info("stderr:\n" + (result.stderr or " [empty]"))

    if result.returncode == 0:
        logger.info(f"Build succeeded: {output}")
        if use_cache:
            save_cache(cache)
    else:
        logger.error(f"Linking failed with code {result.returncode}")

def main():
    parser = argparse.ArgumentParser(description="ForgeBuild 2.6 — Python Build System for C++")
    parser.add_argument("--init", action="store_true", help="Initialize a new project")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--build", action="store_true", help="Build your project")
    parser.add_argument("--sync", action="store_true", help="Sync dependencies from GitHub")
    parser.add_argument("--force-sync", action="store_true", help="Force re-sync of all dependencies")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose compiler output")
    parser.add_argument("--force-rebuild", action="store_true", help="Recompile everything, ignoring cache")

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
    if args.force_rebuild and args.build:
        logger.error("you cannot mix --build and --force-build!")
        exit(1)
    if args.build:
            build_project(verbose=args.verbose, use_cache=True)
    if args.force_rebuild:
            build_project(verbose=args.verbose, use_cache=False)
        
    
            



if __name__ == "__main__":
    main()