import argparse, json, os, subprocess, sys, shutil, stat, hashlib
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='[ForgeBuild] %(levelname)s: %(message)s'
)
logger = logging.getLogger("ForgeBuild")

CACHE_PATH = ".forgebuild/cache.json"

def hash_file(path):
    with open(path, "rb") as f:
        logger.info(f"hashing file: {path}")
        return hashlib.sha256(f.read()).hexdigest()

def load_config(verbose=False):
    try:
        logger.info("loading project configuration data...")
        with open("forgebuild.json", "r") as f:
            data = json.load(f)
            if verbose:
                logger.info(f"project data: {data}")
            return data
        
    except Exception as e:
        logger.fatal(f"Error loading project configuration data: {e}")
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


def run_diagnostics():
    logger.info("Running diagnostics...")

    # 1. Check for compilers
    gcc_path = shutil.which("gcc")
    clang_path = shutil.which("clang")

    if gcc_path:
        logger.info(f"Found GCC at {gcc_path}")
    if clang_path:
        logger.info(f"Found Clang at {clang_path}")
    if not clang_path and not gcc_path:
        logger.error("No supported C++ compiler found (GCC or Clang)")

    # 2. Check for forgebuild.json
    if os.path.isfile("forgebuild.json"):
        logger.info("Found forgebuild.json in current directory")
    else:
        logger.warning("forgebuild.json not found — build config may be missing")

    # 3. Check if cache folder exists
    if os.path.isdir(".forgebuild/cache"):
        logger.info("Cache folder exists")
    else:
        logger.warning("Cache folder missing — builds may be slower or fail")

    logger.info("Diagnostics complete.")

def sync_dependencies(force=False):
    start_sync = time.perf_counter()

    config = load_config()
    deps = config.get("dependencies", [])

    if not isinstance(deps, list):
        logger.error("Invalid format: 'dependencies' must be a list of objects with 'name' and 'repo'")
        return

    include_dir = "include"
    os.makedirs(include_dir, exist_ok=True)

    for dep in deps:
        if not isinstance(dep, dict):
            logger.warning(f"Skipping malformed dependency entry: {dep}")
            continue

        repo = dep.get("repo")
        name = dep.get("name")

        if not repo or not name:
            logger.warning(f"Dependency missing 'name' or 'repo': {dep}")
            continue

        path = os.path.join(include_dir, name)

        if os.path.exists(path):
            if force:
                logger.info(f"Force re-syncing {name} from {repo}")
                shutil.rmtree(path)
            else:
                logger.info(f"Skipping {name} — already cloned")
                continue

        logger.info(f"Cloning {name} from {repo} into {path}")
        clone_start = time.perf_counter()
        result = subprocess.run(["gh", "repo", "clone", repo, path], capture_output=True, text=True)
        clone_end = time.perf_counter()

        logger.info("stdout:\n" + (result.stdout or " [empty]"))
        logger.info("stderr:\n" + (result.stderr or " [empty]"))

        if result.returncode != 0:
            logger.error(f"Failed to clone {repo} — exit code {result.returncode}")
        else:
            logger.info(f"Cloned {name} in {clone_end - clone_start:.2f} seconds")

    end_sync = time.perf_counter()
    logger.info(f"Total dependency sync time: {end_sync - start_sync:.2f} seconds")
  
def build_project(verbose=False, use_cache=False):
    compiled_count = 0
    if not use_cache:
        logger.warning("DISABLING CACHING CAN MAKE BUILDS SLOW! ! !")
    config = load_config(verbose=verbose)
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

            logger.info(f"Compiling {src} -> {obj}")
            cmd = [compiler] + flags + ["-c", src, "-o", obj]
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.info(f"compiler returncode: {result.returncode}")
            if verbose:
                logger.info("stdout:\n" + (result.stdout or " [empty]"))
                logger.info("stderr:\n" + (result.stderr or " [empty]"))
            if result.returncode != 0:
                
                logger.fatal(f"Compilation failed for {src}")
                logger.info("stdout:\n" + (result.stdout or " [empty]"))
                logger.info("stderr:\n" + (result.stderr or " [empty]"))
                return
            cache[src] = src_hash
            compiled_count += 1
        else:
            logger.info(f"Skipping compile of {src} — no changes detected.")

    if not rebuild_needed and use_cache:
        logger.info("Skipping link — no changes detected.")
        prnt = (
        f"{compiled_count} files had to be compiled in this build."
        if compiled_count != 1
        else f"{compiled_count} file had to be compiled in this build."
        )
        logger.info(prnt)
        return

    logger.info(f"Linking: {' and '.join(object_files)} -> {output}")
    cmd = [compiler] + object_files + ["-o", output]
    result = subprocess.run(cmd, capture_output=True, text=True)

    prnt = (
    f"{compiled_count} files had to be compiled in this build."
    if compiled_count != 1
    else f"{compiled_count} file had to be compiled in this build."
    )
    logger.info(prnt)
    if result.returncode == 0:
        logger.info(f"Build succeeded: {output}")

        if use_cache:
            save_cache(cache)
    else:
        logger.critical(f"Linking failed with code {result.returncode}")
        logger.info("stdout:\n" + (result.stdout or " [empty]"))
        logger.info("stderr:\n" + (result.stderr or " [empty]"))
staffroll = [
    "--ForgeBuild 3.0--",
    "",
    "",
    "--PROGRAMMING & DESIGN--",
    "glkdrlgkrlzflnjkgh",
    "",
    "",
    "--SPECIAL THANKS--",
    "GitHub (for making it possible to have this project be open source!)",
    "ForgeBuild is a FOSS Build System for C++, it is licensed under MIT, for more information, go to: ",
    "https://github.com/glkdrlgkrlzflnjkgh/ForgeBuild",
    "",
    ""
    
]
def main():
    parser = argparse.ArgumentParser(description="ForgeBuild 3.0 — Python Build System for C++")
    parser.add_argument("--init", action="store_true", help="Initialize a new project")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--build", action="store_true", help="Build your project")
    parser.add_argument("--sync", action="store_true", help="Sync dependencies from GitHub")
    parser.add_argument("--force-sync", action="store_true", help="Force re-sync of all dependencies")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose compiler output")
    parser.add_argument("--force-rebuild", action="store_true", help="Recompile everything, ignoring cache")
    parser.add_argument("--credits", action="store_true", help="view the credits!")
    args = parser.parse_args()

    if not any(vars(args).values()):
        logger.info("HINT: if you were trying to build, you now need to run forgebuild --build")
        return
    if args.credits:
        for line in staffroll:
            print(line)
            time.sleep(.5)
        return
    if args.init:
        init_project()
    if args.check:
        run_diagnostics()
    if args.sync:
        sync_dependencies(force=args.force_sync)
    if args.force_rebuild and args.build:
        logger.critical("you cannot mix --build and --force-build!")
        exit(1)
    if args.build:
            build_project(verbose=args.verbose, use_cache=True)
    if args.force_rebuild:
            build_project(verbose=args.verbose, use_cache=False)
        
    
            



if __name__ == "__main__":
    main()