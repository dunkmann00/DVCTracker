from pathlib import Path
import click, shutil, subprocess, time

GHP_RESOURCES = [
    "app/static",
    "README.md"
]

DVCTRACKER_GITHUB_URL = "https://github.com/dunkmann00/DVCTracker.git"

GHP_SOURCE_DIR = "gh_pages_source"
GHP_STATIC_BRANCH = "gh-pages-static"
GHP_STATIC_REMOTE = "github-static"

class Git():
    def __init__(self, dir=""):
        dir_path = dir if isinstance(dir, Path) else Path(dir)
        dir_path = dir_path.resolve()
        self._dir = dir_path

    def is_present(self):
        git_dir = self._dir / ".git"
        return git_dir.exists()

    def run(self, *args, errors_ok=False, **kwargs):
        args = ("git", "-C", str(self._dir)) + args
        print(" ".join(args))
        completed_process = subprocess.run(args, **kwargs)
        if not errors_ok:
            completed_process.check_returncode()
        return completed_process

    def fix_git_name(self, name):
        return name.replace("_", "-")

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.run(self.fix_git_name(name), *args, **kwargs)

    def squash_all(self, message, **kwargs):
        # https://stackoverflow.com/a/23486788
        # git reset $(git commit-tree HEAD^{tree} -m "A new start")
        tree_kwargs = kwargs.copy()
        tree_kwargs["text"] = True
        tree_kwargs["stdout"] = subprocess.PIPE
        sha = self.commit_tree("HEAD^{tree}", "-m", message, **tree_kwargs).stdout
        sha = sha.strip() # It puts a newline on the end....wish I realized that sooner -_-
        if not sha:
            raise RuntimeError("Unable to squash, no sha hash returned.")
        return self.reset(sha, **kwargs)

def clean_dir(source_dir, clean_git=False):
    print(f"Cleaning '{source_dir}'{' and removing git directory' if clean_git else ''}...", end="")
    for child in source_dir.iterdir():
        if not clean_git and child.name == ".git":
            continue

        if child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
    print("done.")

def copy_resources(ghp_source_path):
    clean_dir(ghp_source_path)
    print(f"Copying resources into '{ghp_source_path}'...", end="")
    for resource in GHP_RESOURCES:
        path = Path(resource)
        if path.is_file():
            shutil.copy2(path, ghp_source_path)
        else:
            shutil.copytree(path, ghp_source_path / path.name, ignore=shutil.ignore_patterns(".*"), dirs_exist_ok=True)
    print("done.")

def clone_from_github(git, ghp_source_path):
    print("Cloning DVCTracker from Github...")
    ghp_source_path.mkdir(parents=True, exist_ok=True)
    clean_dir(ghp_source_path, clean_git=True)
    git.clone("--branch", GHP_STATIC_BRANCH, "--single-branch", "--origin", GHP_STATIC_REMOTE, DVCTRACKER_GITHUB_URL, ".")

def checkout_static(git):
    if git.branch("--list", GHP_STATIC_BRANCH, text=True, stdout=subprocess.PIPE).stdout:
        print(f"Checking out '{GHP_STATIC_BRANCH}' branch...")
        git.checkout(GHP_STATIC_BRANCH)
    else:
        print(f"Creating and checking out '{GHP_STATIC_BRANCH}' branch...")
        git.checkout("-b", GHP_STATIC_BRANCH)

def commit_and_push(git):
    print("Committing and pushing static assets to Github...")
    message = "DVCTracker Github Pages static assets"
    git.add("--all")
    result = git.diff_index("--quiet", "--cached", "HEAD", errors_ok=True) # First check if there is anything needing to be commited
    if result.returncode:
        git.commit("--message", message) # Another option, instead of using 'diff-index', would be to use '--allow-empty'
    git.squash_all(message)
    git.push(GHP_STATIC_REMOTE, GHP_STATIC_BRANCH, "--force")

@click.command(help=(
    "Copy static folder and other files necessary for Github Pages "
    f"to the '{GHP_SOURCE_DIR}' directory. Then trigger a commit and "
    "push. The upstream will build the jekyll site, making it "
    "accessible through Github Pages. NOTE: This is currently meant "
    "to be run locally."
    )
)
def main():
    ghp_source_path = Path(GHP_SOURCE_DIR)
    git = Git(ghp_source_path)

    if not git.is_present():
        clone_from_github(git, ghp_source_path)

    checkout_static(git)
    copy_resources(ghp_source_path)
    commit_and_push(git)

if __name__ == "__main__":
    main()
