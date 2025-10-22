# ForgeBuild - A FOSS Build System for C++
# Copyright (c) 2025 glkdrlgkrlzflnjkgh and contributors
# Licensed under the MIT License
# See LICENSE file or https://opensource.org/licenses/MIT for details

import argparse, json, os, subprocess, sys, shutil, stat, hashlib, glob 
import logging
import time
import threading
logging.basicConfig(
    level=logging.INFO,
    format='[ForgeBuild] %(levelname)s: %(message)s'
)
logger = logging.getLogger("ForgeBuild")

CACHE_PATH = ".forgebuild/cache.json"

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
        return "ERROR"
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
                # Skip hidden folders or dot-prefixed paths
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
                "sources": ["src/main.cpp"],
                "output": "build/app.exe",
                "compiler": "clang++",
                "flags": ["-Wall"]
            }
        },
        "dependencies": []
    }

    with open("forgebuild.json", "w") as f:
        json.dump(config, f, indent=4)

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


def build_project(verbose=False, use_cache=False, fast=False, jobs=None,comp=None):
    build_timer = time.perf_counter()
    compiled_count = 0
    config = load_config(verbose=verbose)

    target = list(config["targets"].keys())[0]
    tconf = config["targets"][target]

    nocache = tconf["nocache"]
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
    if compiler == 'g++':
        logger.warning("g++ support is EXPERIMENTAL and is NOT recommended for production!")
        logger.warning("g++ is NOT compatible with caching. disabling caching...")
        use_cache = False
    elif compiler == "clang":
        logger.critical("if you were intending to use clang (thinking it was an alias for clang++) it is NOT. please rebuild with clang++!")
        return
    if compiler not in ("g++", "clang++"):
        logger.critical("supported compilers are: clang++ (recommended) and g++ (not recommended)")
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
            logger.warning(f"Could not delete old executable: {e}")

    os.makedirs(".forgebuild/cache", exist_ok=True)

    object_files = []

    def compile_source(src):
        comp_time = time.perf_counter()

        nonlocal compiled_count
        
        obj = os.path.join(".forgebuild", "cache", os.path.basename(src).replace(".cpp", ".forgebin"))

        with object_lock:
            object_files.append(obj)

        with cache_lock:
            src_hash = hash_file(src)
            cached_hash = cache.get(src)

            if verbose:
                logger.info(f"Current hash: {src_hash}")
                logger.info(f"Cached hash: {cached_hash}")

            should_compile = (
                not use_cache or
                cached_hash != src_hash or
                not os.path.exists(obj)
            )

        if should_compile:
            thr_id = threading.get_ident()
            logger.info(f"Compiling {src} -> {obj} on thread {thr_id}")
            cmd = [compiler] + flags + ["-c", src, "-o", obj]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if verbose:
                logger.info("stdout:\n" + (result.stdout or " [empty]"))
                logger.info("stderr:\n" + (result.stderr or " [empty]"))
            if result.returncode != 0:
                logger.fatal(f"Compilation failed for {src}")
                logger.info("build FAILED.")
                logger.info("stdout:\n" + (result.stdout or " [empty]"))
                logger.info("stderr:\n" + (result.stderr or " [empty]"))
                return False
            with cache_lock:
                cache[src] = src_hash
            end = time.perf_counter()
            logger.info(f"thread {thr_id} has finished compiling {src}")
            logger.info(f"thread {thr_id} took: {end - comp_time:.3f}ms")


            compiled_count += 1
        else:
            logger.info(f"Skipping compile of {src} — no changes detected.")
        return True
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        logger.info(f"using: {jobs or os.cpu_count()} threads!")
        futures = {executor.submit(compile_source, src): src for src in sources}
        for future in concurrent.futures.as_completed(futures):
            if future.result() is False:
                logger.critical("Build aborted due to compilation error.")
                return

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
        logger.info(f"Build succeeded: {output}")
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
    logger.info(f"build took: {final_ms}ms")


staffroll = [
    "--ForgeBuild 4.1--",
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
    parser = argparse.ArgumentParser(description="ForgeBuild 4.1 — Python Build System for C++")
    parser.add_argument("--init", action="store_true", help="Initialize a new project")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--build", action="store_true", help="Build your project")
    parser.add_argument("--sync", action="store_true", help="Sync dependencies from GitHub")
    parser.add_argument("--force-sync", action="store_true", help="Force re-sync of all dependencies")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose compiler output")
    parser.add_argument("--force-rebuild", action="store_true", help="Recompile everything, ignoring cache")
    parser.add_argument("--credits", action="store_true", help="view the credits!")
    parser.add_argument("--fast", action="store_true", help="turn on -Ofast, NOT RECOMMENDED!")
    parser.add_argument("--fr", action="store_true", help="see --force-rebuild")
    parser.add_argument("--jobs", type=int, help="Number of parallel compile jobs (default: auto)")
    parser.add_argument('--run', action='store_true', help='Run the compiled executable after build')
    parser.add_argument("--compiler", type=str, help="override the compiler that will be used for compilation and linking")
    args = parser.parse_args()

    if not any(vars(args).values()):
        logger.info("HINT: if you were trying to build, you now need to run forgebuild --build")
        return
    if args.credits:
        for line in staffroll:
            print(line)
            time.sleep(.08)
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
            fst = args.fast
            if args.compiler is not None and not (args.fr or args.force_rebuild):
                logger.critical("force-rebuilding is required when overriding compilers!")
                return
            build_project(verbose=args.verbose, use_cache=True, fast=fst,jobs=args.jobs,comp=args.compiler)
    if args.force_rebuild or args.fr:
            fst = args.fast
            build_project(verbose=args.verbose, use_cache=False, fast=fst,jobs=args.jobs,comp=args.compiler)
    if args.run:
        run_project(verbose=args.verbose)
        
    
            



if __name__ == "__main__":
    main()