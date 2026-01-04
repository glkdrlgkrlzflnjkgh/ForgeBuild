# ForgeBuild - A FOSS Build System for C++
# Copyright (c) 2025 glkdrlgkrlzflnjkgh and contributors
# Licensed under the MIT License
# See LICENSE file or https://opensource.org/licenses/MIT for details

import argparse, json, os, subprocess, sys, shutil, stat, hashlib, glob 
import logging
import time

import threading
handler = logging.StreamHandler()
COMPILER_LOGS = ""
if sys.version_info < (3,10):
    logger.fatal("ForgeBuild requires Python 3.10 or higher! please update your Python installation.")
    sys.exit(1)
SUCCESS_LEVEL = 25
class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[0m",       # White/default
        SUCCESS_LEVEL: "\033[32m",     # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[5;31m"  # Blinking red (careful with this one!)

 # Bold red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"
formatter = ColorFormatter('[ForgeBuild] %(levelname)s: %(message)s')
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
handler.setFormatter(formatter)

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)
def GlitchText(text):
    import random
    # Unicode combining diacritical marks (the real glitch stuff)
    glitch_chars = [chr(i) for i in range(0x0300, 0x036F)]

    glitched = ''
    for char in text:
        if char.isalnum() and random.random() < 0.2:  # 20% chance to glitch
            # Add 1–3 random glitch marks to the character
            glitched += char + ''.join(random.choice(glitch_chars) for _ in range(random.randint(1, 3)))
        else:
            glitched += char

    return glitched
logging.Logger.success = success

logger = logging.getLogger("ForgeBuild")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger = logging.getLogger("ForgeBuild")

CACHE_PATH = ".forgebuild/cache.json"
def parse_dependencies(depfile): 
    try:
        with open(depfile, "r") as f:
            content = f.read()
        # depfile format: target: dep1 dep2 dep3 ...
        parts = content.replace("\\\n", " ").split(":")
        if len(parts) > 1:
            deps = parts[1].split()
            return deps
    except Exception as e:
        logger.error(f"Failed to parse {depfile}: {e}")
    return []
def hash_file(path):
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            size = os.path.getsize(path)
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash {path}: {e}")
        return f"ERROR: {e}"
from pathlib import Path

def expand_sources(source_list):
    expanded = set()
    logger.info("globbing sources... please wait.")
    
    for entry in source_list:
        if "*" in entry:
            base = entry.split("**")[0].rstrip("/")
            pattern = entry.split("/")[-1]
            matched = Path(base).rglob(pattern)
            for path in matched:
                norm = os.path.normpath(str(path))
                # Skip hidden folders or dot-prefixed paths, we ignore dot-prefixed paths to avoid looking in forgebuild's cache folder. since it is independent per project!
                if any(part.startswith('.') for part in Path(norm).parts):
                    continue
                expanded.add(norm)
        else:
            norm = os.path.normpath(entry)
            if any(part.startswith('.') for part in Path(norm).parts):
                continue
            expanded.add(norm)

    # Final deduplication pass
    final_sources = list(expanded)
    for i in final_sources:
        logger.info(f"file search: {i}")
    return final_sources

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

    # 1. Check for compiler
    clang_path = shutil.which("clang")



    if clang_path:
        logger.info(f"Found Clang at {clang_path}")
    else:
        logger.warning("Clang not found in PATH")
    if not clang_path:
        logger.error("No supported C++ compiler found (Clang)") # We dont support G++ anymore, since that is dropped in 5.0

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

    logger.success("Diagnostics complete.")

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
            logger.fatal(f"Malformed dependency entry: {dep}")
            return

        repo = dep.get("repo")
        name = dep.get("name")

        if not repo or not name:
            logger.fatal(f"Dependency missing 'name' or 'repo': {dep}")
            return

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
            logger.success(f"Cloned {name} in {clone_end - clone_start:.2f} seconds")

    end_sync = time.perf_counter()
    logger.info(f"Total dependency sync time: {end_sync - start_sync:.2f} seconds")
def init_project():
    if os.path.exists("forgebuild.json"):
        logging.warning("Project already initialized. Skipping init to avoid overwriting existing files.")
        return

    os.makedirs("src", exist_ok=True)
    os.makedirs("build", exist_ok=True)

    # Write example main.cpp
    hello_code = '''#include <iostream>

int main() {
    std::cout << "Hello, world!" << std::endl;
    return 0;
}
'''
    with open("src/main.cpp", "w") as f:
        f.write(hello_code)

    # Write forgebuild.json
    config = {
        "targets": {
            "app": {
                "nocache" : "no",
                "sources": [
                "src/**/*.cpp",
                "src/**/*.c",
                "include/**/*.cpp",
                "include/**/*.c"
                ],
                "output": "build/app.exe",
                "compiler": "clang++", #FIXME: this field should be removed due to removal of G++ support for 5.0
                "flags": ["-Wall","-Iinclude"]
            }
        },
        "dependencies": []
    }

    with open("forgebuild.json", "w") as f:
        json.dump(config, f, indent=4)
    try:
        os.makedirs("include",exist_ok=True)
    except Exception as e:
        logger.critical(f"something has gone horribly wrong: {e}")
        return

    # Generate PowerShell wrapper
    script_path = os.path.abspath(__file__)
    wrapper_code = f'''# ForgeBuild launcher script
# Usage: .\\forgebuild.ps1 --build (or any other supported ForgeBuild arguments!)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath
echo 'running forgebuild wrapper v1.0...'
echo 'forgebuild is located at: {script_path}'
py "{script_path}" @args
'''
    builder_code = """
./forgebuild --build

"""
    with open("forgebuild.ps1", "w") as f:
        f.write(wrapper_code)
    with open("build.ps1", "w") as f:
        f.write(builder_code)

    logging.info("ForgeBuild project initialized")



import os
import subprocess
import threading
import concurrent.futures

cache_lock = threading.Lock()
object_lock = threading.Lock()
def run_project(verbose=False):
    config = load_config(verbose=verbose)
    target = list(config["targets"].keys())[0]
    tconf = config["targets"][target]
    exe_path = tconf["output"]
    logger.info(f"running compiled EXE... EXE path is {exe_path} ")

    process = subprocess.Popen(
        exe_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # ensures output is decoded to strings
    )

    # Read stdout and stderr line by line
    while True:
        output = process.stdout.readline()
        error = process.stderr.readline()

        if output:
            print(f"{output.strip()}")

        if error:
            print(f"{error.strip()}")

        if output == '' and error == '' and process.poll() is not None:
            break


def build_project(verbose=False, use_cache=False, fast=False, jobs=None,comp=None, argu=None):
    if not argu.sync and not argu.force_sync:
        logger.warning("it is recommended to run --sync before building to ensure all dependencies are up to date! (ignore this if you dont have dependencies or have already synced!)")
    build_timer = time.perf_counter()
    compiled_count = 0
    config = load_config(verbose=verbose)

    target = list(config["targets"].keys())[0]
    tconf = config["targets"][target]

    nocache = tconf.get("nocache", "no") # default to "no" if not specified
    if nocache not in ("yes", "no"):
        logger.error("Invalid value for 'nocache'. Must be 'yes' or 'no'.")
        return

    if nocache == "yes":
        logger.info("ignoring cache because nocache is in the project data file!")
        use_cache = False
    if not use_cache:
        logger.warning("DISABLING CACHING CAN MAKE BUILDS SLOW! ! !")

    cache = load_cache() if use_cache else {}

    compiler = tconf["compiler"]
    if comp != None:
        compiler = comp

    elif compiler == "clang":
        logger.critical("if you were intending to use clang (thinking it was an alias for clang++) it is NOT. please rebuild with clang++!")
        return
    if compiler not in ("clang++"):
        logger.critical("unsupported compiler specified! only clang++ is supported (G++ was removed at 10/12/2025 for the upcoming 5.0 release!)")
        return
    logger.info(f"using compiler: {compiler}")

    flags = tconf["flags"][:]
    if verbose and "-v" not in flags:
        flags.append("-v")
    if fast and "-Ofast" not in flags:
        logger.warning("--fast IS NOT RECOMMENDED!")
        flags.append("-Ofast")

    raw_sources = tconf["sources"]
    sources = expand_sources(raw_sources)

    for sr in sources:
        if os.path.isfile(sr):
            ext = os.path.splitext(sr)[1].lower()
            if ext in [".h", ".hpp"]:
                logger.critical("source files CANNOT be .hpp or .h files!")
                return

    output = tconf["output"]
    exe_path = tconf.get("output", "build/app.exe")  # fallback if not defined
    if os.path.exists(exe_path):
        try:
            os.remove(exe_path)
            logger.info(f"Deleted previous executable: {exe_path}")
        except Exception as e:
            logger.critical(f"Could not delete old executable: {e}")
            return

    os.makedirs(".forgebuild/cache", exist_ok=True)

    object_files = []

    def compile_source(src):
        global COMPILER_LOGS
        comp_time = time.perf_counter()
        nonlocal compiled_count
        
        obj = os.path.join(".forgebuild", "cache", os.path.basename(src).replace(".cpp", ".forgebin"))
        depfile = os.path.join(".forgebuild", "cache", os.path.basename(src).replace(".cpp", ".d"))

        with object_lock:
            object_files.append(obj)

        with cache_lock:
            src_hash = hash_file(src)
            cached_entry = cache.get(src, {})
            cached_cpp_hash = cached_entry.get("cpp_hash")
            cached_headers = cached_entry.get("headers", {})

            if verbose:
                logger.info(f"Current hash: {src_hash}")
                logger.info(f"Cached cpp hash: {cached_cpp_hash}")

            should_compile = (
                not use_cache or
                cached_cpp_hash != src_hash or
                not os.path.exists(obj)
            )

        # Always parse headers if depfile exists
        headers = parse_dependencies(depfile) if os.path.exists(depfile) else []
        header_hashes = {h: hash_file(h) for h in headers if os.path.exists(h)}

        # Detect header changes
        header_changed = any(
            cached_headers.get(h) != header_hashes[h] for h in header_hashes
        )

        if should_compile or header_changed:
            thr_id = threading.get_ident()
            if should_compile:
                logger.info(f"Source file {src} has changed or is not cached.")
            elif header_changed:
                logger.info(f"One or more headers for {src} have changed.")
            logger.info(f"Compiling {src} -> {obj} on thread {thr_id}")

            
            cmd = [compiler] + flags + ["-c", src, "-o", obj, "-MMD", "-MF", depfile]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
            except Exception as e:
                logger.critical("Failed to start compilation process: " + str(e))
                return False

            if verbose:

                COMPILER_LOGS = "STDOUT:" + result.stdout + "\n" + "STDERR:" + result.stderr

            if result.returncode != 0:

                COMPILER_LOGS = "STDOUT:" + result.stdout + "\n" + "STDERR:" + result.stderr
                logger.critical(f"Compilation failed for {src}")
                return False

            with cache_lock:
                cache[src] = {
                    "cpp_hash": src_hash,
                    "headers": header_hashes
                }

            end = time.perf_counter()
            logger.info(f"thread {thr_id} finished compiling {src} in {end - comp_time:.3f}s")
            compiled_count += 1
        else:
            logger.info(f"Skipping compile of {src} — no changes detected.")

        return True

    build_succeed = True # default to true, we'll set to false if any compilation fails    
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        logger.info(f"using: {jobs or os.cpu_count()} threads!")
        futures = {executor.submit(compile_source, src): src for src in sources}
        for future in concurrent.futures.as_completed(futures):
            if not future.result():
                build_succeed = False
                break # exit early on compilation failure
    if not build_succeed:
        logger.critical("Build failed due to compilation errors.")
        logger.info("Compiler logs:\n" + COMPILER_LOGS or "[]empty]")
        return # we do this to avoid linking if compilation failed, since that would waste time and likely fail anyway
    logger.info(f"Linking: {' and '.join(object_files)} into {output}")
    cmd = [compiler] + object_files + ["-o", output]
    result = subprocess.run(cmd, capture_output=True, text=True)

    prnt = (
        f"{compiled_count} files had to be compiled in this build."
        if compiled_count != 1
        else f"{compiled_count} file had to be compiled in this build."
    )
    logger.info(prnt)

    if result.returncode == 0 and result:
        logger.success(f"Build succeeded: {output}")
        logger.info("saving to cache...")
        try:
            with cache_lock:
                save_cache(cache)
        except Exception as e:
            logger.error(f"cache saving failed! {e}")
        logger.info("cache saved!")
    else:
        logger.critical(f"Linking failed with code {result.returncode}")
        logger.info("stdout:\n" + (result.stdout or " [empty]"))
        logger.info("stderr:\n" + (result.stderr or " [empty]"))
    bend = time.perf_counter()
    final_ms = (bend - build_timer) * 1000
    logger.success(f"build took: {final_ms}ms")


staffroll = [
    "--ForgeBuild 5.0--",
    "",
    "",
    "--PROGRAMMING & DESIGN--",
    "glkdrlgkrlzflnjkgh - The big neurodivergent big cheese behind ForgeBuild",
    "AND CONTRIBUTORS",
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
    # Set up command-line argument parser with ForgeBuild description
    parser = argparse.ArgumentParser(description="ForgeBuild 5.0 — Python Build System for C++")

    # Define supported command-line options
    parser.add_argument("--init", action="store_true", help="Initialize a new project")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--build", action="store_true", help="Build your project")
    parser.add_argument("--sync", action="store_true", help="Sync dependencies from GitHub")
    parser.add_argument("--force-sync", action="store_true", help="Force re-sync of all dependencies")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose compiler output")
    parser.add_argument("--force-rebuild", action="store_true", help="Recompile everything, ignoring cache")
    parser.add_argument("--credits", action="store_true", help="View the credits")
    parser.add_argument("--fast", action="store_true", help="Enable -Ofast optimization (NOT RECOMMENDED!)")
    parser.add_argument("--fr", action="store_true", help="Alias for --force-rebuild")
    parser.add_argument("--jobs", type=int, help="Number of parallel compile jobs (default: auto)")
    parser.add_argument("--run", action="store_true", help="Run the compiled executable after build")
    parser.add_argument("--sodium-bad", action="store_true", help=argparse.SUPPRESS)  # hidden easter egg. DO NOT DOCUMENT THIS FLAG. (yes. it is an easter egg. I want to VENGANCE.... EHEHEHE)
    # Parse arguments from command line
    args = parser.parse_args()

    # If no arguments were provided, give a helpful hint and exit
    if not any(vars(args).values()):
        logger.info("HINT: if you were trying to build, you now need to run forgebuild --build")
        return

    # Show credits if requested
    if args.credits:
        for line in staffroll:
            print(line)
            time.sleep(.08)  # small delay for scrolling effect
        return
    if args.sodium_bad:
        msg = """
            jellysquid3, are you reading this?\n
            Well. I am saying this because you gave me a scary legal threat over my Sodium fork.\n
            So here is my message to you:\n
            Stay 120 miles away from my projects unless you want to get bonked by a cartoon hammer.\n

        """
        
        logger.critical(GlitchText(msg))
        return
    # Initialize a new project
    if args.init:
        init_project()

    # Run diagnostics
    if args.check:
        run_diagnostics()

    # Sync dependencies (optionally force re-sync)
    if args.sync:
        sync_dependencies(force=args.force_sync)

    # Prevent mixing --build and --force-rebuild flags
    if (args.force_rebuild or args.fr) and args.build:
        logger.critical("you cannot mix --build and --force-build!")
        exit(1)

    # Handle normal build
    if args.build:
        fst = args.fast
        # If compiler override is requested, force rebuild must be enabled
        # (This is now removed since I have removed G++ support)
        build_project(verbose=args.verbose, use_cache=True, fast=fst, jobs=args.jobs, argu=args)

    # Handle force rebuild (ignores cache)
    if args.force_rebuild or args.fr:
        fst = args.fast
        build_project(verbose=args.verbose, use_cache=False, fast=fst, jobs=args.jobs, argu=args)

    # Run the compiled executable
    if args.run:
        run_project(verbose=args.verbose)


# Entry point: only run main() if script is executed directly
if __name__ == "__main__":
    main()